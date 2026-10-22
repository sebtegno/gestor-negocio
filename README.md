# Gestor de Negocio (Stock + Cotizaciones + Facturación ARCA)

App de escritorio en Python para manejar stock de productos, generar
cotizaciones para clientes y convertirlas en facturas electrónicas
autorizadas por ARCA (ex AFIP).

## Instalación

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

pip install PySide6 SQLAlchemy reportlab requests beautifulsoup4
```

`pyafipws` se instala aparte cuando conectes el módulo de ARCA (ver abajo);
no es necesario para usar Stock, Clientes y Cotizaciones.

## Ejecutar

```bash
python run.py
```

Esto crea automáticamente `negocio.db` (SQLite) en la raíz del proyecto la
primera vez que corrés la app.

## Estado actual del proyecto

✅ **Funcionando:**
- **Pestaña Inicio**: fecha del día, cotización del dólar del Banco Nación
  (compra/venta), y un lugar para tu logo. Se consulta al BNA una vez por
  día y se cachea en la base — el botón "Actualizar cotización" fuerza
  una nueva consulta. Para el logo, colocá un archivo `logo.png` dentro
  de la carpeta `assets/` (ver `assets/LEEME.txt`).
- Alta, edición y baja (desactivación) de productos, con control de
  stock mínimo (alerta visual), buscador por código/descripción, y la
  opción de marcar un producto como "Precio en dólares (USD)": en ese
  caso, el precio se carga en USD y se convierte automáticamente a pesos
  con la cotización del día al armar una cotización.
  "Eliminar" desactiva el producto (no lo borra físicamente) para no
  romper el historial de cotizaciones y remitos que ya lo referencian.
- Registro de movimientos de stock (entrada/salida/ajuste) — función lista
  en `app/repositorio.py::registrar_movimiento_stock`, falta agregarle un
  botón en la interfaz de Stock si lo querés usar desde ahí.
- Alta, edición, baja y buscador de clientes, con condición frente al IVA
  y dirección/datos de envío (localidad, provincia, código postal, notas).
- **Perfil de cliente** (doble clic en la fila o botón "Ver perfil"):
  - Dirección de envío editable.
  - **Cuenta corriente**: saldo (debe/haber), historial de movimientos,
    carga de pagos y deudas manuales, y edición/eliminación de cualquier
    movimiento por si hay un error de carga. Facturar una cotización
    genera automáticamente un "debe" por el total.
  - **Remitos**: generación desde una cotización del cliente (copia los
    ítems y cantidades), y **descarga en PDF** lista para imprimir
    (botón "Descargar PDF", abre el explorador de archivos para elegir
    dónde guardarlo).
- Alta, edición, baja y buscador de cotizaciones (por cliente o número).
  Al crear o editar una cotización:
  - Tanto el cliente como los productos se eligen con un combo con
    **autocompletado** (escribís parte del nombre, CUIT, código o
    descripción y filtra en vivo).
  - Si agregás el mismo producto más de una vez, **se suman las
    cantidades** en la misma línea en vez de duplicarla.
  - Si el producto está marcado como "Precio en dólares", el precio se
    **multiplica automáticamente por la cotización del día** (venta) y
    se muestra tanto el precio final en pesos como el origen en USD,
    antes de guardar. Ese precio en pesos queda "congelado" en la
    cotización, así el historial no cambia si mañana el dólar es otro.
  - Se puede **descargar la cotización en PDF** (te lo ofrece justo
    después de crearla, o con el botón "Descargar PDF" en cualquier
    momento).
  - Casilla **"Incluir IVA"**: si la tildás, se suma el IVA de cada
    producto (según su alícuota, 21% por defecto) y ves subtotal, IVA y
    total antes de guardar. El PDF muestra el mismo desglose.
- **Aceptar una cotización sin facturar**: el botón "Aceptar (descuenta
  stock)" pasa la cotización a estado Aceptada y descuenta el stock. Cada
  cotización lleva una marca de "stock ya descontado", así que si después
  la facturás **no se descuenta por segunda vez**, y tampoco se puede
  aceptar dos veces ni aceptar una ya facturada. Una cotización aceptada
  no se puede editar ni eliminar; "Revertir aceptación" devuelve el stock
  y la deja de nuevo en Borrador (solo si todavía no fue facturada).
- Conversión de una cotización en factura (registro local, estado
  "Pendiente"), que hereda los importes ya calculados (con o sin IVA),
  **descuenta el stock** de cada producto (dejando registro del
  movimiento) y genera el "debe" en la cuenta corriente. Si algún
  producto no tiene stock suficiente, avisa y no factura nada.

🚧 **Falta conectar (requiere tus datos reales de ARCA):**
- `app/afip/wsfe_client.py` tiene la estructura completa para emitir
  contra el webservice WSFEv1, pero el método `autenticar()` está sin
  completar porque necesita:
  1. Que instales `pyafipws`: `pip install pyafipws`
  2. Que coloques tu certificado (`certificado.crt`) y clave privada
     (`clave.key`) dentro de la carpeta `certs/`.
  3. Que definas tu CUIT y si vas a operar en homologación (testing) o
     producción.

  El docstring del método `autenticar()` en ese archivo tiene el código
  exacto para completarlo.
- Conectar el botón "Convertir a factura" de la pestaña Cotizaciones para
  que, además de crear el registro local, llame a `ClienteWSFE.autorizar_factura()`
  y guarde el CAE con `repo.marcar_factura_emitida(...)`.
- Generación del PDF de la factura (con CAE y código QR obligatorio de
  ARCA) — no implementado todavía.

## Crear el .exe (sin instalar Python en las demás PCs)

1. En la PC donde vas a armarlo (una sola vez), instalá Python 3.10 o
   superior desde python.org, marcando "Add Python to PATH".
2. Hacé doble clic en `construir_exe.bat`. Instala lo necesario, arma el
   programa y tarda varios minutos.
3. Vas a encontrar `dist\GestorNegocio.exe`. Copiá esa carpeta `dist`
   donde quieras (por ejemplo `C:\GestorNegocio`). Ese `.exe` corre en
   cualquier Windows sin instalar Python ni ninguna librería.

Detalles a tener en cuenta:
- La base de datos (`negocio.db`), el logo (`assets\logo.png`), los
  certificados (`certs\`) y el registro de errores (`error.log`) viven
  **junto al .exe**, no adentro. Para llevarte tus datos actuales,
  copiá tu `negocio.db` al lado del `.exe`. Para cambiar el logo,
  reemplazá `assets\logo.png` sin reconstruir nada.
- Si ponés el `.exe` en una carpeta donde Windows no deja escribir
  (por ejemplo "Archivos de programa"), guarda todo en
  `%LOCALAPPDATA%\GestorNegocio`. Conviene usar una carpeta común.
- Si querés un ícono propio, dejá un `icono.ico` en `assets\` antes de
  construir.
- El `.exe` abre sin consola; si algo falla, el detalle queda en
  `error.log`.
- Algunos antivirus desconfían de los `.exe` armados con PyInstaller la
  primera vez. Si pasa, agregá una excepción para esa carpeta.
- Cada vez que se cambie el código hay que volver a correr
  `construir_exe.bat` para generar un `.exe` nuevo.

## Aspecto visual

Toda la identidad visual (nombre, colores, tipografía) está en
`app/marca.py`; los estilos de Qt están en `app/ui/tema.py`. Para
acercarla a la web de la empresa, cambiá los códigos de color de
`marca.py` y reiniciá la app: la interfaz y los PDF los toman de ahí.
La paleta incluida es provisoria. Fuerza un aspecto claro aunque Windows
esté en modo oscuro.

## Actualizar la app sin perder datos

Al iniciar, la app agrega automáticamente a tu `negocio.db` las columnas
nuevas que falten (por ejemplo IVA o dólar), sin borrar lo que ya cargaste.

## Sobre la cotización del dólar

Se obtiene scrapeando `https://www.bna.com.ar/Cotizador/MonedasHistorico`
(la tabla de "divisas" que publica el BNA, sin necesidad de JavaScript).
Se guarda en la base una vez por día; si en algún momento no hay conexión
a internet, la app usa el último valor guardado en caché en vez de
romperse. Si el BNA cambia el diseño de esa página en el futuro, el
scraper puede dejar de funcionar — el error te lo va a indicar
claramente en la pestaña Inicio.

## Sobre eliminar registros

Para no dejar datos huérfanos:
- **Productos**: "Eliminar" los desactiva (quedan ocultos, pero se
  conserva el historial en cotizaciones/remitos viejos).
- **Clientes**: solo se pueden eliminar si no tienen cotizaciones,
  movimientos de cuenta corriente ni remitos asociados.
- **Cotizaciones**: solo se pueden eliminar si todavía no tienen una
  factura o un remito generado (en ese caso, cambiá su estado a
  "Cancelada" en su lugar). Tampoco se pueden editar una vez facturadas.

## Estructura

```
gestor_negocio/
├── app/
│   ├── database.py       # Modelos SQLAlchemy (Producto, Cliente, Cotización, Factura...)
│   ├── repositorio.py     # Toda la lógica de negocio (CRUD, stock, cotizaciones)
│   ├── main.py             # Punto de entrada
│   ├── afip/
│   │   └── wsfe_client.py  # Integración con ARCA (WSFEv1) — pendiente de conectar
│   ├── pdf_generator.py     # Genera el PDF de cotizaciones y remitos (reportlab)
│   ├── rutas.py             # Dónde se guardan datos, logo y certificados (script o .exe)
│   ├── marca.py             # Nombre, colores y tipografía (un solo lugar)
│   ├── cotizador_dolar.py   # Caché diaria + fallback de la cotización del dólar
│   ├── servicios/
│   │   └── dolar_bna.py     # Scraping de la cotización del dólar del BNA
│   └── ui/
│       ├── main_window.py
│       ├── inicio_view.py      # Logo, fecha y cotización del dólar
│       ├── stock_view.py
│       ├── clientes_view.py
│       ├── cliente_perfil.py   # Cuenta corriente + remitos por cliente
│       ├── cotizaciones_view.py
│       └── widgets.py          # Combo con autocompletado reutilizable
├── assets/
│   └── logo.png             # Poné acá tu logo (se ve en la pestaña Inicio)
├── certs/                  # Poné acá tu certificado.crt y clave.key (NO subir a git)
├── requirements.txt
├── construir_exe.bat        # Genera dist\GestorNegocio.exe
└── run.py
```

## Importante sobre ARCA

ARCA no tiene un "archivo para importar facturas" genérico: la forma
oficial de emitir facturas electrónicas desde una app propia es el
webservice **WSFEv1**, que devuelve el CAE (Código de Autorización
Electrónico) en el momento. Por eso esta app está armada para conectarse
directo al webservice en vez de generar un archivo intermedio.

Antes de facturar en producción, probá siempre primero contra el ambiente
de **homologación** (testing) de ARCA con tu certificado de prueba.


## Imprimir remitos sobre el formulario preimpreso
Formulario de 18,5 x 25 cm. En el perfil del cliente > Remitos: **Imprimir en formulario** genera un PDF solo con los datos
(tamaño 185x250 mm, imprimir al 100 %, sin "ajustar a página"). **Vista previa** lo muestra sobre una imagen del formulario
(`assets/remito_fondo.png`). **Ajustar impresión** permite corregir desplazamiento X/Y, modo hoja A4 y generar una hoja de prueba.
Imprimí primero la prueba sobre un formulario sobrante y ajustá los mm.
