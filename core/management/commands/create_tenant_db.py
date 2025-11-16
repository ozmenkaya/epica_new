"""
Management command to create a new tenant database.

Usage:
    python manage.py create_tenant_db helmex
    python manage.py create_tenant_db acme --db-password secret123

This will:
1. Create PostgreSQL database (epica_helmex)
2. Create database user
3. Grant permissions
4. Run migrations
5. Create superuser (optional)
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import connection
import os
import subprocess
import sys


class Command(BaseCommand):
    help = 'Create a new tenant database for an organization'

    def add_arguments(self, parser):
        parser.add_argument(
            'tenant_slug',
            type=str,
            help='Organization slug (e.g., helmex, acme)'
        )
        parser.add_argument(
            '--db-name',
            type=str,
            help='Database name (default: epica_{slug})'
        )
        parser.add_argument(
            '--db-user',
            type=str,
            help='Database user (default: epica_{slug})'
        )
        parser.add_argument(
            '--db-password',
            type=str,
            help='Database password (randomly generated if not provided)'
        )
        parser.add_argument(
            '--db-host',
            type=str,
            default='localhost',
            help='Database host (default: localhost)'
        )
        parser.add_argument(
            '--db-port',
            type=str,
            default='5432',
            help='Database port (default: 5432)'
        )
        parser.add_argument(
            '--skip-migrations',
            action='store_true',
            help='Skip running migrations'
        )
        parser.add_argument(
            '--create-superuser',
            action='store_true',
            help='Create superuser after setup'
        )

    def handle(self, *args, **options):
        tenant_slug = options['tenant_slug'].lower()
        db_name = options.get('db_name') or f'epica_{tenant_slug}'
        db_user = options.get('db_user') or f'epica_{tenant_slug}'
        db_password = options.get('db_password') or self._generate_password()
        db_host = options['db_host']
        db_port = options['db_port']
        
        self.stdout.write(self.style.SUCCESS(f'\n=== Creating Tenant Database ==='))
        self.stdout.write(f'Tenant Slug: {tenant_slug}')
        self.stdout.write(f'Database Name: {db_name}')
        self.stdout.write(f'Database User: {db_user}')
        self.stdout.write(f'Database Host: {db_host}:{db_port}')
        
        # Check if using PostgreSQL
        if 'postgresql' not in settings.DATABASES['default']['ENGINE']:
            self.stdout.write(
                self.style.WARNING(
                    '\nWarning: Not using PostgreSQL. Multi-tenant DB isolation works best with PostgreSQL.'
                )
            )
        
        # Step 1: Create database and user in PostgreSQL
        self.stdout.write(f'\n[1/4] Creating PostgreSQL database and user...')
        if not self._create_postgres_database(db_name, db_user, db_password):
            raise CommandError('Failed to create database')
        
        # Step 2: Add to Django settings (dynamically)
        self.stdout.write(f'\n[2/4] Configuring Django database connection...')
        db_url = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
        env_var = f'TENANT_DB_{tenant_slug.upper()}'
        
        self.stdout.write(f'\nAdd this to your .env file:')
        self.stdout.write(self.style.SUCCESS(f'{env_var}={db_url}'))
        
        # Step 3: Run migrations
        if not options['skip_migrations']:
            self.stdout.write(f'\n[3/4] Running migrations...')
            # Temporarily add database to settings
            import dj_database_url
            settings.DATABASES[f'tenant_{tenant_slug}'] = dj_database_url.parse(db_url, conn_max_age=600)
            
            # Run migrations on new database
            self._run_migrations(f'tenant_{tenant_slug}')
        
        # Step 4: Summary
        self.stdout.write(f'\n[4/4] Setup complete!')
        self.stdout.write(self.style.SUCCESS('\n✅ Tenant database created successfully!'))
        
        self.stdout.write(f'\n📝 Next Steps:')
        self.stdout.write(f'1. Add to .env file:')
        self.stdout.write(f'   {env_var}={db_url}')
        self.stdout.write(f'2. Restart Django server')
        self.stdout.write(f'3. Access via subdomain: http://{tenant_slug}.epica.com.tr')
        self.stdout.write(f'4. Or via query param: http://epica.com.tr/?org={tenant_slug}')
        
        if options['create_superuser']:
            self.stdout.write(f'\n[Optional] Creating superuser...')
            self._create_superuser(f'tenant_{tenant_slug}')
    
    def _generate_password(self):
        """Generate a random secure password."""
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*()"
        return ''.join(secrets.choice(alphabet) for i in range(16))
    
    def _create_postgres_database(self, db_name, db_user, db_password):
        """Create PostgreSQL database and user using psql."""
        
        # SQL commands
        sql_commands = f"""
-- Create user if not exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = '{db_user}') THEN
        CREATE USER {db_user} WITH PASSWORD '{db_password}';
    END IF;
END
$$;

-- Create database if not exists
SELECT 'CREATE DATABASE {db_name} OWNER {db_user}'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '{db_name}')\\gexec

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {db_user};
"""
        
        # Get postgres connection info from default database
        default_db = settings.DATABASES['default']
        
        # Try to extract connection info
        try:
            # For dj_database_url parsed configs
            pg_host = default_db.get('HOST', 'localhost')
            pg_port = default_db.get('PORT', '5432')
            pg_user = default_db.get('USER', 'postgres')
            
            # Write SQL to temp file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
                f.write(sql_commands)
                sql_file = f.name
            
            # Run psql command
            cmd = [
                'psql',
                '-h', pg_host,
                '-p', str(pg_port),
                '-U', pg_user,
                '-f', sql_file,
                'postgres'  # Connect to postgres database to create new DB
            ]
            
            self.stdout.write(f'Running: psql -h {pg_host} -p {pg_port} -U {pg_user} -f {sql_file} postgres')
            self.stdout.write(self.style.WARNING('You may be prompted for PostgreSQL password...'))
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Clean up temp file
            os.unlink(sql_file)
            
            if result.returncode == 0:
                self.stdout.write(self.style.SUCCESS('✅ Database created successfully'))
                return True
            else:
                self.stdout.write(self.style.ERROR(f'❌ Error: {result.stderr}'))
                self.stdout.write(self.style.WARNING('\nAlternative: Run these SQL commands manually:'))
                self.stdout.write(sql_commands)
                return False
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error: {str(e)}'))
            self.stdout.write(self.style.WARNING('\nRun these SQL commands manually as postgres user:'))
            self.stdout.write(sql_commands)
            return False
    
    def _run_migrations(self, db_alias):
        """Run Django migrations on specific database."""
        from django.core.management import call_command
        
        try:
            call_command('migrate', '--database', db_alias, verbosity=1)
            self.stdout.write(self.style.SUCCESS('✅ Migrations completed'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Migration error: {str(e)}'))
            self.stdout.write('You can run migrations manually later with:')
            self.stdout.write(f'  python manage.py migrate --database={db_alias}')
    
    def _create_superuser(self, db_alias):
        """Create superuser on specific database."""
        from django.core.management import call_command
        
        try:
            call_command('createsuperuser', '--database', db_alias)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error: {str(e)}'))
