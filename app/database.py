"""
Capa de base de datos del sistema.
Usa SQLite local (archivo negocio.db) a través de SQLAlchemy.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime,
    ForeignKey, Text, Boolean, inspect, text
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from .rutas import ruta_base_de_datos

DB_PATH = ruta_base_de_datos()
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------

class Producto(Base):
    __tablename__ = "productos"

    id = Column(Integer, primary_key=True)
    codigo = Column(String(50), unique=True, nullable=False)
    descripcion = Column(String(255), nullable=False)
    precio_costo = Column(Float, default=0.0)
    precio_venta = Column(Float, default=0.0)
    stock_actual = Column(Float, default=0.0)
    stock_minimo = Column(Float, default=0.0)
    unidad = Column(String(20), default="unidad")
    alicuota_iva = Column(Float, default=21.0)  # % IVA
    activo = Column(Boolean, default=True)
    precio_en_dolares = Column(Boolean, default=False)
    # Si es True, precio_costo y precio_venta están expresados en USD
    # y se convierten a pesos con la cotización del día al cotizar/facturar.

    movimientos = relationship("MovimientoStock", back_populates="producto")

    @property
    def stock_bajo(self) -> bool:
        return self.stock_actual <= self.stock_minimo


class MovimientoStock(Base):
    """Historial de entradas/salidas de stock, para trazabilidad."""
    __tablename__ = "movimientos_stock"

    id = Column(Integer, primary_key=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    fecha = Column(DateTime, default=dt.datetime.now)
    tipo = Column(String(20))  # "entrada" | "salida" | "ajuste"
    cantidad = Column(Float)
    motivo = Column(String(255))

    producto = relationship("Producto", back_populates="movimientos")


class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True)
    razon_social = Column(String(255), nullable=False)
    cuit = Column(String(20))
    condicion_iva = Column(String(50), default="Consumidor Final")
    # RI, Monotributo, Exento, Consumidor Final
    domicilio = Column(String(255))  # domicilio fiscal
    email = Column(String(150))
    telefono = Column(String(50))

    # Datos de envío (pueden diferir del domicilio fiscal)
    domicilio_envio = Column(String(255))
    localidad_envio = Column(String(100))
    provincia_envio = Column(String(100))
    codigo_postal_envio = Column(String(20))
    notas_envio = Column(Text)  # ej: horarios de recepción, contacto en depósito, etc.

    cotizaciones = relationship("Cotizacion", back_populates="cliente")
    movimientos_cuenta = relationship(
        "MovimientoCuentaCorriente", back_populates="cliente",
        cascade="all, delete-orphan", order_by="MovimientoCuentaCorriente.fecha"
    )
    remitos = relationship("Remito", back_populates="cliente")

    @property
    def saldo(self) -> float:
        """Positivo = el cliente nos debe. Negativo = a favor del cliente."""
        return sum(
            m.importe if m.tipo == "debe" else -m.importe
            for m in self.movimientos_cuenta
        )


class Cotizacion(Base):
    __tablename__ = "cotizaciones"

    id = Column(Integer, primary_key=True)
    numero = Column(String(20), unique=True)
    fecha = Column(DateTime, default=dt.datetime.now)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    estado = Column(String(20), default="Borrador")
    # Borrador | Enviada | Aceptada | Facturada | Cancelada
    validez_dias = Column(Integer, default=15)
    notas = Column(Text)
    incluye_iva = Column(Boolean, default=False)
    # Si es True, se suma el IVA de cada producto (según su alícuota) al total.
    stock_descontado = Column(Boolean, default=False)
    # True cuando el stock de esta cotización ya se descontó (al aceptarla o
    # al facturarla). Evita descontar dos veces.

    cliente = relationship("Cliente", back_populates="cotizaciones")
    items = relationship("ItemCotizacion", back_populates="cotizacion",
                          cascade="all, delete-orphan")
    factura = relationship("Factura", back_populates="cotizacion", uselist=False)

    @property
    def subtotal_neto(self) -> float:
        return sum(i.subtotal for i in self.items)

    @property
    def monto_iva(self) -> float:
        if not self.incluye_iva:
            return 0.0
        return sum(i.subtotal * (i.producto.alicuota_iva / 100) for i in self.items)

    @property
    def total(self) -> float:
        return self.subtotal_neto + self.monto_iva


class ItemCotizacion(Base):
    __tablename__ = "items_cotizacion"

    id = Column(Integer, primary_key=True)
    cotizacion_id = Column(Integer, ForeignKey("cotizaciones.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Float, default=1.0)
    precio_unitario = Column(Float, default=0.0)  # siempre en pesos (ARS)
    descuento_pct = Column(Float, default=0.0)

    # Si el producto está dolarizado, acá queda registrado con qué precio en
    # USD y con qué cotización del día se calculó precio_unitario, para que
    # el historial no cambie si mañana el dólar vale otra cosa.
    precio_usd_original = Column(Float)
    tipo_cambio_usado = Column(Float)

    cotizacion = relationship("Cotizacion", back_populates="items")
    producto = relationship("Producto")

    @property
    def subtotal(self) -> float:
        bruto = self.cantidad * self.precio_unitario
        return bruto * (1 - self.descuento_pct / 100)


class Factura(Base):
    """Comprobante emitido contra ARCA (o pendiente de emitir)."""
    __tablename__ = "facturas"

    id = Column(Integer, primary_key=True)
    cotizacion_id = Column(Integer, ForeignKey("cotizaciones.id"), unique=True)
    tipo_comprobante = Column(String(5))  # "A" | "B"
    punto_venta = Column(Integer, default=1)
    numero = Column(Integer)  # asignado por ARCA
    fecha_emision = Column(DateTime)
    cae = Column(String(20))
    cae_vencimiento = Column(DateTime)
    importe_total = Column(Float)
    estado = Column(String(20), default="Pendiente")
    # Pendiente | Emitida | Error
    error_detalle = Column(Text)

    cotizacion = relationship("Cotizacion", back_populates="factura")


class MovimientoCuentaCorriente(Base):
    """
    Cuenta corriente por cliente: cada factura/cotización entregada genera
    un "debe" (deuda) y cada cobro genera un "haber" (pago).
    """
    __tablename__ = "movimientos_cuenta_corriente"

    id = Column(Integer, primary_key=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    fecha = Column(DateTime, default=dt.datetime.now)
    tipo = Column(String(10))  # "debe" | "haber"
    concepto = Column(String(255))
    importe = Column(Float, default=0.0)
    medio_pago = Column(String(50))  # efectivo, transferencia, etc. (solo "haber")

    cliente = relationship("Cliente", back_populates="movimientos_cuenta")


class Remito(Base):
    """Remito de entrega, generado a partir de una cotización."""
    __tablename__ = "remitos"

    id = Column(Integer, primary_key=True)
    numero = Column(String(20), unique=True)
    fecha = Column(DateTime, default=dt.datetime.now)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    cotizacion_id = Column(Integer, ForeignKey("cotizaciones.id"))
    domicilio_entrega = Column(String(255))
    estado = Column(String(20), default="Pendiente")  # Pendiente | Entregado
    observaciones = Column(Text)
    orden_compra = Column(String(50))
    expreso = Column(String(100))
    numero_formulario = Column(String(30))  # Nº preimpreso (solo registro)

    cliente = relationship("Cliente", back_populates="remitos")
    cotizacion = relationship("Cotizacion")
    items = relationship("ItemRemito", back_populates="remito",
                          cascade="all, delete-orphan")


class ItemRemito(Base):
    __tablename__ = "items_remito"

    id = Column(Integer, primary_key=True)
    remito_id = Column(Integer, ForeignKey("remitos.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Float, default=1.0)

    remito = relationship("Remito", back_populates="items")
    producto = relationship("Producto")


class ValorDolar(Base):
    """
    Caché diario de la cotización del dólar (Banco Nación), para no golpear
    la web del BNA en cada operación: se guarda una vez por día.
    """
    __tablename__ = "valores_dolar"

    id = Column(Integer, primary_key=True)
    fecha = Column(DateTime, unique=True, nullable=False)  # solo se usa la parte de fecha
    compra = Column(Float)
    venta = Column(Float)
    fuente = Column(String(100), default="BNA")
    obtenido_en = Column(DateTime, default=dt.datetime.now)


class Proveedor(Base):
    """Proveedores: aparte de los clientes, no aparecen al armar cotizaciones."""
    __tablename__ = "proveedores"

    id = Column(Integer, primary_key=True)
    razon_social = Column(String(200), nullable=False)
    cuit = Column(String(20))
    condicion_iva = Column(String(50))
    domicilio = Column(String(255))
    email = Column(String(120))
    telefono = Column(String(50))
    notas = Column(Text)
    activo = Column(Boolean, default=True)


class FacturaProveedor(Base):
    __tablename__ = "facturas_proveedor"

    id = Column(Integer, primary_key=True)
    proveedor_id = Column(Integer, ForeignKey("proveedores.id"), nullable=False)
    numero = Column(String(50))
    fecha = Column(DateTime, default=dt.datetime.now)
    total = Column(Float, default=0.0)
    observaciones = Column(Text)
    archivo = Column(String(500))  # ruta del PDF/imagen original, si se cargó
    stock_aplicado = Column(Boolean, default=False)

    proveedor = relationship("Proveedor")
    items = relationship("ItemFacturaProveedor", back_populates="factura",
                          cascade="all, delete-orphan")


class ItemFacturaProveedor(Base):
    __tablename__ = "items_factura_proveedor"

    id = Column(Integer, primary_key=True)
    factura_id = Column(Integer, ForeignKey("facturas_proveedor.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"))  # None = no se sumó al stock
    descripcion = Column(String(300))
    cantidad = Column(Float, default=1.0)
    precio_unitario = Column(Float, default=0.0)
    stock_sumado = Column(Float, default=0.0)

    factura = relationship("FacturaProveedor", back_populates="items")
    producto = relationship("Producto")


class MovimientoCuentaProveedor(Base):
    """Cuenta corriente con el proveedor. Debe = lo que le debemos (facturas); Haber = lo que le pagamos."""
    __tablename__ = "movimientos_cuenta_proveedor"

    id = Column(Integer, primary_key=True)
    proveedor_id = Column(Integer, ForeignKey("proveedores.id"), nullable=False)
    fecha = Column(DateTime, default=dt.datetime.now)
    tipo = Column(String(10))  # "debe" | "haber"
    concepto = Column(String(255))
    importe = Column(Float, default=0.0)
    medio_pago = Column(String(50))
    factura_id = Column(Integer, ForeignKey("facturas_proveedor.id"))


class AliasProductoProveedor(Base):
    """Recuerda qué producto del stock corresponde a cada descripción de un proveedor."""
    __tablename__ = "alias_producto_proveedor"

    id = Column(Integer, primary_key=True)
    proveedor_id = Column(Integer, ForeignKey("proveedores.id"), nullable=False)
    texto = Column(String(300), nullable=False)  # descripción normalizada
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)


def init_db() -> None:
    Base.metadata.create_all(engine)
    _migrar_columnas_faltantes()


def _migrar_columnas_faltantes() -> None:
    """
    Si el archivo negocio.db ya existía de una versión anterior de la app
    (por ejemplo, antes de agregar el IVA o el dólar), esto agrega las
    columnas nuevas que falten sin borrar los datos existentes.
    """
    inspector = inspect(engine)
    with engine.begin() as conn:
        for tabla in Base.metadata.tables.values():
            if not inspector.has_table(tabla.name):
                continue  # tabla nueva, ya se creó completa arriba
            columnas_existentes = {c["name"] for c in inspector.get_columns(tabla.name)}
            for columna in tabla.columns:
                if columna.name in columnas_existentes:
                    continue
                tipo_sql = columna.type.compile(engine.dialect)
                conn.execute(text(
                    f'ALTER TABLE "{tabla.name}" ADD COLUMN "{columna.name}" {tipo_sql}'
                ))


def get_session():
    return SessionLocal()
