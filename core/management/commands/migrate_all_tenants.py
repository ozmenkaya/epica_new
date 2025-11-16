"""
Management command to migrate all tenant databases.

Usage:
    python manage.py migrate_all_tenants
    python manage.py migrate_all_tenants --tenant helmex
    python manage.py migrate_all_tenants --fake

This will run migrations on all configured tenant databases.
"""

from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings
import os


class Command(BaseCommand):
    help = 'Run migrations on all tenant databases'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant',
            type=str,
            help='Migrate only specific tenant (slug)'
        )
        parser.add_argument(
            '--fake',
            action='store_true',
            help='Mark migrations as run without actually running them'
        )
        parser.add_argument(
            '--fake-initial',
            action='store_true',
            help='Fake initial migrations if tables already exist'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== Migrating Tenant Databases ===\n'))
        
        # Get all tenant databases
        tenant_databases = self._get_tenant_databases()
        
        if not tenant_databases:
            self.stdout.write(self.style.WARNING('No tenant databases configured.'))
            self.stdout.write('Configure tenant databases in .env file:')
            self.stdout.write('  TENANT_DB_HELMEX=postgresql://user:pass@localhost/epica_helmex')
            return
        
        # Filter by specific tenant if requested
        specific_tenant = options.get('tenant')
        if specific_tenant:
            specific_db = f'tenant_{specific_tenant.lower()}'
            tenant_databases = {k: v for k, v in tenant_databases.items() if k == specific_db}
            
            if not tenant_databases:
                self.stdout.write(
                    self.style.ERROR(f'Tenant database not found: {specific_tenant}')
                )
                return
        
        # Migrate each tenant database
        total = len(tenant_databases)
        success = 0
        failed = 0
        
        for idx, (db_alias, db_config) in enumerate(tenant_databases.items(), 1):
            tenant_slug = db_alias.replace('tenant_', '')
            db_name = db_config.get('NAME', 'unknown')
            
            self.stdout.write(f'\n[{idx}/{total}] Migrating: {tenant_slug}')
            self.stdout.write(f'Database: {db_name}')
            self.stdout.write('-' * 60)
            
            try:
                # Build migrate command args
                migrate_args = ['--database', db_alias]
                
                if options['fake']:
                    migrate_args.append('--fake')
                
                if options['fake_initial']:
                    migrate_args.append('--fake-initial')
                
                # Run migrations
                call_command('migrate', *migrate_args, verbosity=1)
                
                self.stdout.write(self.style.SUCCESS(f'✅ {tenant_slug} migrated successfully'))
                success += 1
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'❌ {tenant_slug} migration failed: {str(e)}'))
                failed += 1
        
        # Summary
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS(f'\n✅ Migration Summary:'))
        self.stdout.write(f'Total tenants: {total}')
        self.stdout.write(self.style.SUCCESS(f'Successful: {success}'))
        if failed > 0:
            self.stdout.write(self.style.ERROR(f'Failed: {failed}'))
    
    def _get_tenant_databases(self):
        """Get all tenant database configurations."""
        tenant_dbs = {}
        
        for db_alias, db_config in settings.DATABASES.items():
            if db_alias.startswith('tenant_'):
                tenant_dbs[db_alias] = db_config
        
        return tenant_dbs
