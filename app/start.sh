# start.sh 

#!/bin/bash

function start_development() {
    echo "Running development server..."
    python manage.py runserver 0.0.0.0:8002
}

function start_production() {
    echo "Running production server..."
    gunicorn megatron.wsgi -w 4 -b 0.0.0.0:8002 --log-file -
}

if [ ${PRODUCTION} == "false" ]; then
    # use development server
    start_development
else
    # use production server
    start_production
fi
