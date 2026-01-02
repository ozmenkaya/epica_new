"""
Epica Healthcheck & Monitoring Views
Bu dosyayı core/views.py dosyasının en altına ekleyin
veya ayrı bir monitoring/views.py olarak kullanın
"""

from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
from django.conf import settings
import os
import psutil
import time


def healthcheck(request):
    """
    Basit healthcheck endpoint - load balancer/uptime monitoring için
    GET /health/
    """
    return JsonResponse({
        "status": "healthy",
        "timestamp": time.time()
    })


def healthcheck_detailed(request):
    """
    Detaylı sistem durumu - sadece yetkili kullanıcılar için
    GET /health/detailed/
    """
    # Basit auth check - sadece staff veya özel token
    auth_token = request.headers.get('X-Health-Token', '')
    expected_token = getattr(settings, 'HEALTH_CHECK_TOKEN', 'epica-health-2024')
    
    if not (request.user.is_staff or auth_token == expected_token):
        return JsonResponse({"error": "Unauthorized"}, status=401)
    
    checks = {
        "status": "healthy",
        "timestamp": time.time(),
        "checks": {}
    }
    
    # 1. Database check
    try:
        start = time.time()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_time = (time.time() - start) * 1000
        checks["checks"]["database"] = {
            "status": "ok",
            "response_time_ms": round(db_time, 2)
        }
    except Exception as e:
        checks["checks"]["database"] = {
            "status": "error",
            "error": str(e)
        }
        checks["status"] = "unhealthy"
    
    # 2. Disk space check
    try:
        disk = psutil.disk_usage('/')
        media_disk = psutil.disk_usage('/mnt/HC_Volume_104123408') if os.path.exists('/mnt/HC_Volume_104123408') else None
        
        checks["checks"]["disk"] = {
            "status": "ok" if disk.percent < 90 else "warning",
            "root": {
                "total_gb": round(disk.total / (1024**3), 2),
                "used_gb": round(disk.used / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "percent": disk.percent
            }
        }
        
        if media_disk:
            checks["checks"]["disk"]["media_volume"] = {
                "total_gb": round(media_disk.total / (1024**3), 2),
                "used_gb": round(media_disk.used / (1024**3), 2),
                "free_gb": round(media_disk.free / (1024**3), 2),
                "percent": media_disk.percent
            }
        
        if disk.percent >= 90 or (media_disk and media_disk.percent >= 90):
            checks["status"] = "warning"
            
    except Exception as e:
        checks["checks"]["disk"] = {
            "status": "error",
            "error": str(e)
        }
    
    # 3. Memory check
    try:
        memory = psutil.virtual_memory()
        checks["checks"]["memory"] = {
            "status": "ok" if memory.percent < 90 else "warning",
            "total_gb": round(memory.total / (1024**3), 2),
            "available_gb": round(memory.available / (1024**3), 2),
            "percent": memory.percent
        }
        if memory.percent >= 90:
            checks["status"] = "warning"
    except Exception as e:
        checks["checks"]["memory"] = {
            "status": "error",
            "error": str(e)
        }
    
    # 4. CPU check
    try:
        cpu_percent = psutil.cpu_percent(interval=0.5)
        checks["checks"]["cpu"] = {
            "status": "ok" if cpu_percent < 90 else "warning",
            "percent": cpu_percent,
            "count": psutil.cpu_count()
        }
    except Exception as e:
        checks["checks"]["cpu"] = {
            "status": "error",
            "error": str(e)
        }
    
    # 5. Backup check (son yedekleme ne zaman yapıldı)
    try:
        backup_log = "/mnt/HC_Volume_104123408/backups/backup_history.log"
        if os.path.exists(backup_log):
            with open(backup_log, 'r') as f:
                lines = f.readlines()
                if lines:
                    last_backup = lines[-1].strip().split('|')
                    checks["checks"]["backup"] = {
                        "status": "ok",
                        "last_backup": last_backup[0] if len(last_backup) > 0 else "unknown",
                        "type": last_backup[1] if len(last_backup) > 1 else "unknown"
                    }
                else:
                    checks["checks"]["backup"] = {
                        "status": "warning",
                        "message": "No backup history found"
                    }
        else:
            checks["checks"]["backup"] = {
                "status": "warning",
                "message": "Backup history file not found"
            }
    except Exception as e:
        checks["checks"]["backup"] = {
            "status": "error",
            "error": str(e)
        }
    
    # HTTP status code based on health
    status_code = 200 if checks["status"] == "healthy" else (503 if checks["status"] == "unhealthy" else 200)
    
    return JsonResponse(checks, status=status_code)


def system_metrics(request):
    """
    Prometheus-compatible metrics endpoint
    GET /metrics/
    """
    auth_token = request.headers.get('X-Health-Token', '')
    expected_token = getattr(settings, 'HEALTH_CHECK_TOKEN', 'epica-health-2024')
    
    if not (request.user.is_staff or auth_token == expected_token):
        return JsonResponse({"error": "Unauthorized"}, status=401)
    
    try:
        # Collect metrics
        disk = psutil.disk_usage('/')
        memory = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0.5)
        
        # Prometheus format
        metrics = []
        
        # CPU
        metrics.append(f"# HELP epica_cpu_percent CPU usage percentage")
        metrics.append(f"# TYPE epica_cpu_percent gauge")
        metrics.append(f"epica_cpu_percent {cpu}")
        
        # Memory
        metrics.append(f"# HELP epica_memory_percent Memory usage percentage")
        metrics.append(f"# TYPE epica_memory_percent gauge")
        metrics.append(f"epica_memory_percent {memory.percent}")
        metrics.append(f"# HELP epica_memory_available_bytes Available memory in bytes")
        metrics.append(f"# TYPE epica_memory_available_bytes gauge")
        metrics.append(f"epica_memory_available_bytes {memory.available}")
        
        # Disk
        metrics.append(f"# HELP epica_disk_percent Disk usage percentage")
        metrics.append(f"# TYPE epica_disk_percent gauge")
        metrics.append(f"epica_disk_percent {disk.percent}")
        metrics.append(f"# HELP epica_disk_free_bytes Free disk space in bytes")
        metrics.append(f"# TYPE epica_disk_free_bytes gauge")
        metrics.append(f"epica_disk_free_bytes {disk.free}")
        
        from django.http import HttpResponse
        return HttpResponse("\n".join(metrics), content_type="text/plain")
        
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
