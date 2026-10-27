#!/bin/sh
set -e

if [ -n "$POSTGRES_HOST" ]; then
    echo "Waiting for PostgreSQL at $POSTGRES_HOST:${POSTGRES_PORT:-5432}..."
    while ! python -c "import socket,sys; socket.create_connection(('$POSTGRES_HOST', ${POSTGRES_PORT:-5432}), 2)" 2>/dev/null; do
        sleep 1
    done
fi

python manage.py migrate --noinput
python manage.py collectstatic --noinput

if [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    python manage.py shell -c "
from django.contrib.auth import get_user_model
import os
User = get_user_model()
email = os.environ['DJANGO_SUPERUSER_EMAIL']
if User.objects.filter(email=email).exists():
    print('Superuser already exists:', email)
else:
    User.objects.create_superuser(
        email=email,
        password=os.environ['DJANGO_SUPERUSER_PASSWORD'],
        first_name=os.environ.get('DJANGO_SUPERUSER_FIRST_NAME', 'Admin'),
        last_name=os.environ.get('DJANGO_SUPERUSER_LAST_NAME', 'User'),
    )
    print('Superuser created:', email)
"
fi

exec "$@"
