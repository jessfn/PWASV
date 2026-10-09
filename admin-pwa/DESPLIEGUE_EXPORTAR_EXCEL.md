# Despliegue: botón "Excel completo" (Configuración > Gestión de Datos)

Commit: `62a1ddb`. Cambia el backend (`backend/main.py`, `backend/requirements.txt`) y el panel (`admin-pwa`).
Se despliega igual que `pwasuper/deploy.sh`: el servidor hace `git pull`, compila y copia `dist/`.
Ejecutar **en el servidor** (por SSH). Ajusta las rutas marcadas con `# AJUSTAR` si difieren.

## 1. Traer los cambios
```bash
cd /var/www/PWASV            # AJUSTAR: carpeta donde está clonado el repositorio
git pull origin main
```

## 2. Backend (apipwa.sembrandodatos.com)
```bash
cd /var/www/PWASV/backend
pip install -r requirements.txt        # instala xlsxwriter==3.2.9
```
Reiniciar el servicio del backend de la forma en que ya lo corren:
```bash
# si corre como servicio systemd (AJUSTAR el nombre):
sudo systemctl restart <nombre-del-servicio>
# si se inicia a mano, como indica INSTRUCCIONES_DESPLIEGUE.md:
pkill -f "python.*main.py"; nohup python main.py > backend.log 2>&1 &
```
Verificar (debe responder 401, no 404):
```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://apipwa.sembrandodatos.com/admin/exportar-base/actividades
```

## 3. Panel admin (admin.sembrandodatos.com)
```bash
cd /var/www/PWASV/admin-pwa
npm install && npm run build
sudo cp -r dist/* /var/www/admin.sembrandodatos.com/     # AJUSTAR: carpeta publicada del panel
sudo chown -R www-data:www-data /var/www/admin.sembrandodatos.com/
```
Si el panel usa service worker, limpiar caché del navegador para ver el botón.

## 4. Probar
Entrar al panel > Configuración > Gestión de Datos > **Excel completo** > elegir una base > Generar Excel > Descargar.
Nota: los archivos generados se guardan en la carpeta temporal del servidor (`/tmp/psv_exports`) y se borran solos a las 3 h.
Un Excel de actividades completas pesa ~125 MB y tarda unos minutos; revisar que `client_max_body_size`/timeouts de nginx no limiten la descarga (solo aplica a respuestas largas, no a subidas).
