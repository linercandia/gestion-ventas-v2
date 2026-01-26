# 📊 Sistema de Gestión de Ventas & Automatización de Inventarios

Este proyecto es una solución integral para el control operativo de ventas, diseñada para centralizar la información de múltiples zonas y automatizar el flujo de datos hacia reportes gerenciales en la nube.

## 🚀 Enfoque en Automatización y Gestión de Datos

El sistema transforma procesos manuales en flujos de trabajo digitales eficientes:

* **Sincronización Asíncrona con Google Sheets**: Cada movimiento (carga, traspaso o cierre) se replica automáticamente en Google Sheets mediante su API, eliminando la necesidad de digitación manual al final del día.
* **Integridad de Datos Interzonas**: Implementa una lógica de "confirmación mutua" para transferencias de productos, asegurando que el inventario nunca se pierda en el tránsito entre vendedores.
* **Arquitectura de Sesiones Independientes**: Gestión avanzada de sesiones mediante UUIDs, permitiendo que múltiples vendedores operen de forma aislada y segura, garantizando la trazabilidad por usuario.
* **Reportabilidad Dinámica**: Generación automatizada de reportes consolidados en Excel (`.xlsx`) con cálculos precisos de inventario de salida vs. retorno.



## 🛠️ Stack Tecnológico

* **Core**: Python 3.x & Django Web Framework.
* **Persistencia de Datos**: SQLite (Desarrollo) / PostgreSQL (Producción).
* **Automatización**: Google Sheets API (gspread) & OAuth2.
* **Gestión de Archivos**: OpenPyXL para procesamiento de hojas de cálculo.
* **Interfaz**: HTML5/CSS3 con diseño orientado a la experiencia del vendedor (UX).

## 📋 Estructura de la Solución

* `Jornadas`: Control maestro para habilitar o deshabilitar la operación diaria.
* `Portal Vendedor`: Interfaz optimizada para el registro de movimientos en tiempo real.
* `Admin Panel`: Tablero de control para la gestión de productos, zonas y auditoría de movimientos.

## ⚙️ Instalación y Configuración

1.  **Clonar repositorio**: `git clone https://github.com/linercandia/gestion-ventas-django.git`
2.  **Entorno Virtual**: 
    ```bash
    python -m venv venv
    venv\Scripts\activate
    ```
3.  **Dependencias**: `pip install -r requirements.txt`
4.  **Credenciales**: Colocar el archivo `credenciales.json` (Service Account de Google Cloud) en la raíz del proyecto para habilitar la automatización de Sheets.
5.  **Migraciones**: `python manage.py migrate`

## 🔒 Seguridad
Este repositorio utiliza protección de secretos para evitar la exposición de llaves API. La configuración local está aislada mediante `.gitignore`.
