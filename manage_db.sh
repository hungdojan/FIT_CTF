#/bin/bash

mkdir -p ./db/data/{mongo,redis}

if [[ ! -f ".env" ]]; then
    echo "Missing .env file"
    exit 1
fi

case "$1" in
    "start")
        cd db && podman-compose --env-file ../.env up -d
        ;;
    "stop")
        cd db && podman-compose --env-file ../.env down
        ;;
    "validate")
        cd db && podman-compose --env-file ../.env config
        ;;
    *)
        echo "Missing argument!"
        echo "Usage:"
        echo "./start_db.sh (start|stop|validate)"
        exit 1
        ;;
esac

