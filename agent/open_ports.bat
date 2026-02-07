@echo off
echo ============================================
echo   Alaska Agent - Firewall Configuration
echo ============================================
echo.
echo Este script abrira los puertos UDP necesarios
echo para WebRTC (Control Remoto).
echo.
echo Ejecute como ADMINISTRADOR.
echo.
pause

echo.
echo [1/2] Agregando regla de entrada UDP...
netsh advfirewall firewall add rule name="Alaska WebRTC (UDP Inbound)" dir=in action=allow protocol=UDP localport=10000-60000

echo.
echo [2/2] Agregando regla de salida UDP...
netsh advfirewall firewall add rule name="Alaska WebRTC (UDP Outbound)" dir=out action=allow protocol=UDP localport=10000-60000

echo.
echo ============================================
echo   Configuracion Completada
echo ============================================
echo.
echo Los puertos UDP 10000-60000 estan abiertos.
echo.
pause
