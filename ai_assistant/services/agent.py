"""
AI Agent service - handles conversation with OpenAI and function calling
"""
import logging
import json
from typing import List, Dict, Any, Optional, Generator
from django.conf import settings
from openai import OpenAI
from ai_assistant.services.retriever import RetrieverService
from ai_assistant.services import actions

logger = logging.getLogger(__name__)


class AIAgent:
    """Main AI agent for handling conversations and actions"""
    
    def __init__(self, organization, user):
        self.organization = organization
        self.user = user
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL
        self.retriever = RetrieverService()
    
    def get_system_prompt(self) -> str:
        """
        Get the system prompt for the AI assistant
        
        Returns:
            System prompt text
        """
        return f"""You are an intelligent assistant for Epica, a SaaS platform for managing customer tickets and supplier quotes.

You are helping {self.user.email} from {self.organization.name}.

Your capabilities:
1. Answer questions about tickets, quotes, suppliers, and other data
2. Analyze trends and provide insights
3. Execute actions like updating tickets, sending emails, creating categories

When answering questions:
- Use the provided context from the database
- Be concise and specific
- Include relevant numbers and data
- If you're not sure, say so

When executing actions:
- Always confirm what action you're about to take
- Explain the result clearly
- Only perform actions the user has permission for

Current date: Today

Be helpful, professional, and accurate."""
    
    def get_available_functions(self) -> List[Dict[str, Any]]:
        """
        Get list of available functions for OpenAI function calling
        
        Returns:
            List of function definitions
        """
        return [
            {
                "name": "search_tickets",
                "description": "Search for tickets in the database with filters",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for tickets"
                        },
                        "status": {
                            "type": "string",
                            "enum": ["pending", "quoted", "approved", "ordered", "completed", "cancelled"],
                            "description": "Filter by ticket status"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results",
                            "default": 10
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "get_ticket_stats",
                "description": "Get statistics about tickets (counts, averages, etc.)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "period": {
                            "type": "string",
                            "enum": ["today", "week", "month", "year", "all"],
                            "description": "Time period for statistics"
                        }
                    },
                    "required": ["period"]
                }
            },
            {
                "name": "update_ticket_status",
                "description": "Update the status of a ticket",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ticket_id": {
                            "type": "integer",
                            "description": "ID of the ticket to update"
                        },
                        "new_status": {
                            "type": "string",
                            "enum": ["pending", "quoted", "approved", "ordered", "completed", "cancelled"],
                            "description": "New status for the ticket"
                        }
                    },
                    "required": ["ticket_id", "new_status"]
                }
            },
            {
                "name": "search_suppliers",
                "description": "Search for suppliers and get their information",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for suppliers"
                        }
                    },
                    "required": ["query"]
                }
            }
        ]
    
    def execute_function(self, function_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a function call from the AI
        
        Args:
            function_name: Name of the function to execute
            arguments: Arguments for the function
            
        Returns:
            Function execution result
        """
        try:
            if function_name == "search_tickets":
                return actions.search_tickets(self.organization, self.user, **arguments)
            elif function_name == "get_ticket_stats":
                return actions.get_ticket_stats(self.organization, **arguments)
            elif function_name == "update_ticket_status":
                return actions.update_ticket_status(self.organization, self.user, **arguments)
            elif function_name == "search_suppliers":
                return actions.search_suppliers(self.organization, **arguments)
            else:
                return {"error": f"Unknown function: {function_name}"}
        except Exception as e:
            logger.error(f"Error executing function {function_name}: {e}")
            return {"error": str(e)}
    
    def chat(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Process a user message and generate response
        
        Args:
            message: User message
            conversation_history: Previous messages in conversation
            
        Returns:
            Response dict with assistant message and metadata
        """
        # Get relevant context from database
        context = self.retriever.get_context_for_query(self.organization, message)
        
        # Build messages for OpenAI
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
        ]
        
        # Add conversation history
        if conversation_history:
            messages.extend(conversation_history)
        
        # Add context and user message
        messages.append({
            "role": "user",
            "content": f"{context}\n\nUser question: {message}"
        })
        
        try:
            # Call OpenAI with function calling
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=[{"type": "function", "function": func} for func in self.get_available_functions()],
                tool_choice="auto",
                temperature=0.7,
                max_tokens=1500
            )
            
            message_response = response.choices[0].message
            
            # Check if function call was made
            if message_response.tool_calls:
                # Execute function calls
                function_results = []
                for tool_call in message_response.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    logger.info(f"Executing function: {function_name} with args: {function_args}")
                    result = self.execute_function(function_name, function_args)
                    function_results.append({
                        "name": function_name,
                        "result": result
                    })
                
                # Add function results to messages and get final response
                messages.append(message_response)
                for tool_call, func_result in zip(message_response.tool_calls, function_results):
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(func_result["result"])
                    })
                
                # Get final response
                final_response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=1500
                )
                
                return {
                    "content": final_response.choices[0].message.content,
                    "function_calls": function_results,
                    "tokens_used": response.usage.total_tokens + final_response.usage.total_tokens
                }
            
            return {
                "content": message_response.content,
                "function_calls": [],
                "tokens_used": response.usage.total_tokens
            }
            
        except Exception as e:
            logger.error(f"Error in chat: {e}")
            return {
                "content": f"I encountered an error: {str(e)}",
                "function_calls": [],
                "tokens_used": 0
            }
    
    def stream_chat(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Generator[str, None, None]:
        """
        Stream chat response (for real-time UI updates)
        
        Args:
            message: User message
            conversation_history: Previous messages
            
        Yields:
            Chunks of assistant response
        """
        context = self.retriever.get_context_for_query(self.organization, message)
        
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
        ]
        
        if conversation_history:
            messages.extend(conversation_history)
        
        messages.append({
            "role": "user",
            "content": f"{context}\n\nUser question: {message}"
        })
        
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                temperature=0.7,
                max_tokens=1500
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error(f"Error in stream_chat: {e}")
            yield f"Error: {str(e)}"
