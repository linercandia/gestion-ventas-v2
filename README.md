# Sistema de Gestion de Ventas

Proyecto Django para administrar jornadas de venta, zonas, productos, vendedores, envios entre zonas, informes operativos, pagos y desprendibles.

## Version de Python

Este proyecto queda preparado para trabajar con `Python 3.13`.

Archivos agregados para esto:

- `.python-version`
- `runtime.txt`

## Instalacion

1. Clonar el repositorio:

```bash
git clone https://github.com/linercandia/gestion-ventas-v2.git
cd gestion-ventas-v2
```

2. Verificar que Python 3.13 este instalado:

```bash
py -3.13 --version
```

3. Crear el entorno virtual con Python 3.13:

```bash
py -3.13 -m venv venv
venv\Scripts\activate
```

4. Instalar dependencias:

```bash
pip install -r requirements.txt
```

5. Ejecutar migraciones:

```bash
python manage.py migrate
```

6. Iniciar el servidor:

```bash
python manage.py runserver
```

## Nota importante

En esta maquina el entorno virtual actual sigue corriendo con `Python 3.14`, porque `Python 3.13` no esta instalado localmente. El proyecto ya quedo configurado para 3.13, pero para usarlo realmente en esa version debes recrear el `venv` con:

```bash
py -3.13 -m venv venv
```

## Credenciales opcionales

Si vas a usar la sincronizacion con Google Sheets, debes colocar el archivo `creds.json` en la raiz del proyecto.
