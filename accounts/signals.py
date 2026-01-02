import os
import subprocess
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings
from .models import Organization


@receiver(post_save, sender=Organization)
def create_tenant_database(sender, instance, created, **kwargs):
    """
    Automatically create tenant database and .env entry when a new Organization is created.
    """
    if not created:
        return
    
    slug = instance.slug
    
    # Skip if in test mode
    if settings.TESTING:
        return
    
    # Path to tenant database
    tenant_db_dir = os.path.join(settings.BASE_DIR, "tenant_dbs")
    os.makedirs(tenant_db_dir, exist_ok=True)
    
    db_path = os.path.join(tenant_db_dir, f"db_{slug}.sqlite3")
    
    # Check if database already exists
    if os.path.exists(db_path):
        print(f"Database for {slug} already exists at {db_path}")
        return
    
    # Copy main database to tenant database
    main_db = settings.DATABASES['default']['NAME']
    try:
        import shutil
        shutil.copy2(main_db, db_path)
        print(f"Created tenant database: {db_path}")
    except Exception as e:
        print(f"Error creating tenant database: {e}")
        return
    
    # Add to .env file
    env_path = os.path.join(settings.BASE_DIR, '.env')
    env_key = f"TENANT_DB_{slug.upper().replace('-', '_')}"
    env_value = f"sqlite:///{db_path}"
    
    try:
        # Check if entry already exists
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                if env_key in f.read():
                    print(f"Environment variable {env_key} already exists")
                    return
        
        # Append to .env
        with open(env_path, 'a') as f:
            f.write(f"\n{env_key}={env_value}\n")
        print(f"Added {env_key} to .env")
        
    except Exception as e:
        print(f"Error updating .env file: {e}")


@receiver(post_delete, sender=Organization)
def delete_tenant_database(sender, instance, **kwargs):
    """
    Automatically delete tenant database and .env entry when an Organization is deleted.
    """
    slug = instance.slug
    
    # Skip if in test mode
    if settings.TESTING:
        return
    
    # Path to tenant database
    tenant_db_dir = os.path.join(settings.BASE_DIR, "tenant_dbs")
    db_path = os.path.join(tenant_db_dir, f"db_{slug}.sqlite3")
    
    # Delete database file if it exists
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
            print(f"Deleted tenant database: {db_path}")
        except Exception as e:
            print(f"Error deleting tenant database: {e}")
    
    # Remove from .env file
    env_path = os.path.join(settings.BASE_DIR, '.env')
    env_key = f"TENANT_DB_{slug.upper().replace('-', '_')}"
    
    try:
        if not os.path.exists(env_path):
            return
        
        # Read all lines
        with open(env_path, 'r') as f:
            lines = f.readlines()
        
        # Filter out the tenant DB line
        filtered_lines = [line for line in lines if not line.startswith(env_key)]
        
        # Write back
        with open(env_path, 'w') as f:
            f.writelines(filtered_lines)
        
        print(f"Removed {env_key} from .env")
        
    except Exception as e:
        print(f"Error updating .env file: {e}")
