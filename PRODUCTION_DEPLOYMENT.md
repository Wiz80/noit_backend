# 🚀 Guía de Despliegue en Producción

Esta guía te ayudará a desplegar de forma segura tu aplicación en producción usando Docker Compose.

## 📋 Cambios Realizados para Seguridad

### 🔐 Variables de Entorno Seguras
Se han reemplazado todos los valores hardcodeados por variables de entorno:

- **PostgreSQL**: Credenciales de base de datos principal y Kestra
- **Redis**: Contraseña de autenticación 
- **Taskiq**: Token de API seguro
- **Kestra**: Credenciales de administrador
- **Puertos**: Configurables para diferentes entornos

### 🛡️ Mejoras de Seguridad Implementadas

1. **Autenticación Redis**: Ahora requiere contraseña
2. **Kestra BasicAuth**: Habilitado por defecto en producción
3. **Puertos Configurables**: Permite cambiar puertos por defecto
4. **Credenciales Únicas**: Cada servicio tiene sus propias credenciales

## 🚀 Pasos para Desplegar en Producción

### 1. Generar Variables de Entorno Seguras

```bash
# Hacer el script ejecutable
chmod +x generate_secure_env.sh

# Generar variables seguras
./generate_secure_env.sh > .env
```

### 2. Personalizar Variables de Entorno

Edita el archivo `.env` generado y personaliza:

```bash
# Cambiar dominios y emails
KESTRA_ADMIN_EMAIL=admin@tudominio.com
KESTRA_URL=https://kestra.tudominio.com/

# Ajustar puertos si es necesario
APP_PORT=8000
NGINX_HTTP_PORT=80
NGINX_HTTPS_PORT=443
```

### 3. Configurar Seguridad del Archivo .env

```bash
# Establecer permisos restrictivos
chmod 600 .env

# Verificar que .env está en .gitignore
echo ".env" >> .gitignore
```

### 4. Configurar Certificados SSL

Para HTTPS en producción, configura certificados SSL:

```bash
# Ejemplo con Let's Encrypt
sudo certbot --nginx -d tudominio.com -d kestra.tudominio.com
```

### 5. Desplegar los Servicios

```bash
# Desplegar en producción
docker-compose -f docker-compose.prod.yml up -d

# Verificar que todos los servicios están corriendo
docker-compose -f docker-compose.prod.yml ps

# Ver logs si hay problemas
docker-compose -f docker-compose.prod.yml logs -f
```

## 🔧 Configuración de Nginx

Asegúrate de que tu configuración de Nginx incluya:

### SSL/TLS
```nginx
server {
    listen 443 ssl http2;
    server_name tudominio.com;
    
    ssl_certificate /etc/letsencrypt/live/tudominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/tudominio.com/privkey.pem;
    
    # Configuración SSL segura
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    
    location / {
        proxy_pass http://app:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 🔒 Lista de Verificación de Seguridad

### ✅ Antes del Despliegue
- [ ] Archivo `.env` con contraseñas seguras generadas
- [ ] Permisos correctos en `.env` (600)
- [ ] `.env` incluido en `.gitignore`
- [ ] Certificados SSL configurados
- [ ] Puertos de firewall configurados correctamente
- [ ] Copias de seguridad de datos configuradas

### ✅ Después del Despliegue
- [ ] Todos los servicios corriendo correctamente
- [ ] Conexiones HTTPS funcionando
- [ ] Autenticación funcionando en todos los servicios
- [ ] Logs sin errores críticos
- [ ] Monitoreo configurado

## 🚨 Variables de Entorno Críticas

### Obligatorias
- `POSTGRES_PASSWORD`: Contraseña base de datos principal
- `KESTRA_POSTGRES_PASSWORD`: Contraseña base de datos Kestra
- `REDIS_PASSWORD`: Contraseña Redis
- `TASKIQ_ADMIN_API_TOKEN`: Token API Taskiq
- `KESTRA_ADMIN_PASSWORD`: Contraseña admin Kestra

### Recomendadas
- `KESTRA_ADMIN_EMAIL`: Email del administrador
- `KESTRA_URL`: URL pública de Kestra

## 🔧 Comandos Útiles

### Gestión de Servicios
```bash
# Ver estado de servicios
docker-compose -f docker-compose.prod.yml ps

# Reiniciar un servicio específico
docker-compose -f docker-compose.prod.yml restart app

# Ver logs en tiempo real
docker-compose -f docker-compose.prod.yml logs -f

# Actualizar servicios
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d
```

### Mantenimiento
```bash
# Backup de base de datos
docker-compose -f docker-compose.prod.yml exec postgres pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup.sql

# Limpieza de recursos Docker
docker system prune -a
```

## 🆘 Solución de Problemas

### Problema: Servicio no inicia
```bash
# Ver logs detallados
docker-compose -f docker-compose.prod.yml logs servicio_problema

# Verificar variables de entorno
docker-compose -f docker-compose.prod.yml config
```

### Problema: Conexión de base de datos
```bash
# Verificar conexión PostgreSQL
docker-compose -f docker-compose.prod.yml exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT 1;"
```

### Problema: Redis no accesible
```bash
# Verificar conexión Redis
docker-compose -f docker-compose.prod.yml exec redis redis-cli auth $REDIS_PASSWORD ping
```

## 📞 Soporte

Si encuentras problemas:

1. Revisa los logs de los servicios
2. Verifica que todas las variables de entorno están configuradas
3. Confirma que los puertos no están siendo utilizados por otros servicios
4. Asegúrate de que los certificados SSL son válidos

## 🔄 Rotación de Credenciales

Para rotar credenciales periódicamente:

1. Genera nuevas credenciales con `./generate_secure_env.sh`
2. Actualiza el archivo `.env`
3. Reinicia los servicios: `docker-compose -f docker-compose.prod.yml restart`

---

**⚠️ IMPORTANTE**: Nunca commites el archivo `.env` al repositorio. Mantén las credenciales seguras y úsalas solo en producción. 