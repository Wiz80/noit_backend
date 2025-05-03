#!/bin/sh

# Esperar a que Nginx esté listo
sleep 10

# Verificar si ya tenemos certificados
if [ ! -d /etc/letsencrypt/live/$DOMAIN ]; then
  echo "Solicitando certificados nuevos para $DOMAIN y $DOMAIN_WWW"
  certbot certonly --webroot --webroot-path=/var/www/certbot \
    --email $EMAIL --agree-tos --no-eff-email \
    -d $DOMAIN -d $DOMAIN_WWW || exit 1
  
  # Crear el archivo de mapeo para Nginx
  echo "$DOMAIN 1;" > /etc/nginx/ssl_map.conf
  echo "$DOMAIN_WWW 1;" >> /etc/nginx/ssl_map.conf
  
  # Señal a Nginx para recargar
  nginx -s reload
fi

# Bucle de renovación
trap exit TERM
while :; do
  certbot renew --quiet
  
  # En caso de renovación, asegurarse de que el mapeo está actualizado
  if [ -d /etc/letsencrypt/live/$DOMAIN ]; then
    echo "$DOMAIN 1;" > /etc/nginx/ssl_map.conf
    echo "$DOMAIN_WWW 1;" >> /etc/nginx/ssl_map.conf
    nginx -s reload
  fi
  
  sleep 12h & wait $!
done 