"""
Funciones de acceso y manipulación de datos.
Mantiene la lógica separada de la interfaz gráfica.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from .database import (
    get_session, Producto, MovimientoStock, Cliente,
    Cotizacion, ItemCotizacion, Factura,
    MovimientoCuentaCorriente, Remito, ItemRemito, ValorDolar,
    Proveedor, FacturaProveedor, ItemFacturaProveedor,
    MovimientoCuentaProveedor, AliasProductoProveedor,
)


# ---------------------------------------------------------------------------
# Productos / Stock
# ---------------------------------------------------------------------------

def listar_productos(solo_activos: bool = True) -> list[Producto]:
    with get_session() as s:
        q = select(Producto)
        if solo_activos:
            q = q.where(Producto.activo.is_(True))
        return list(s.execute(q).scalars().all())


def crear_producto(codigo: str, descripcion: str, precio_costo: float,
                    precio_venta: float, stock_inicial: float = 0.0,
                    stock_minimo: float = 0.0, unidad: str = "unidad",
                    alicuota_iva: float = 21.0, precio_en_dolares: bool = False) -> Producto:
    with get_session() as s:
        p = Producto(
            codigo=codigo, descripcion=descripcion,
            precio_costo=precio_costo, precio_venta=precio_venta,
            stock_actual=stock_inicial, stock_minimo=stock_minimo,
            unidad=unidad, alicuota_iva=alicuota_iva,
            precio_en_dolares=precio_en_dolares,
        )
        s.add(p)
        s.commit()
        s.refresh(p)
        return p


def actualizar_producto(producto_id: int, **campos) -> None:
    with get_session() as s:
        p = s.get(Producto, producto_id)
        if not p:
            raise ValueError("Producto no encontrado")
        for k, v in campos.items():
            setattr(p, k, v)
        s.commit()


def registrar_movimiento_stock(producto_id: int, tipo: str, cantidad: float,
                                motivo: str = "") -> None:
    """tipo: 'entrada' | 'salida' | 'ajuste'"""
    with get_session() as s:
        p = s.get(Producto, producto_id)
        if not p:
            raise ValueError("Producto no encontrado")
        if tipo == "entrada":
            p.stock_actual += cantidad
        elif tipo == "salida":
            if cantidad > p.stock_actual:
                raise ValueError("Stock insuficiente para la salida")
            p.stock_actual -= cantidad
        elif tipo == "ajuste":
            p.stock_actual = cantidad
        else:
            raise ValueError("Tipo de movimiento inválido")

        mov = MovimientoStock(producto_id=producto_id, tipo=tipo,
                               cantidad=cantidad, motivo=motivo)
        s.add(mov)
        s.commit()


def obtener_producto(producto_id: int) -> Optional[Producto]:
    with get_session() as s:
        return s.get(Producto, producto_id)


def eliminar_producto(producto_id: int) -> None:
    """
    Desactiva el producto (no lo borra físicamente) para no romper el
    historial de cotizaciones, remitos y movimientos de stock que ya lo
    referencian. Desaparece de los listados normales.
    """
    with get_session() as s:
        p = s.get(Producto, producto_id)
        if not p:
            raise ValueError("Producto no encontrado")
        p.activo = False
        s.commit()


def productos_con_stock_bajo() -> list[Producto]:
    return [p for p in listar_productos() if p.stock_bajo]


# ---------------------------------------------------------------------------
# Clientes
# ---------------------------------------------------------------------------

def listar_clientes() -> list[Cliente]:
    with get_session() as s:
        return list(s.execute(select(Cliente)).scalars().all())


def crear_cliente(razon_social: str, cuit: str = "", condicion_iva: str = "Consumidor Final",
                   domicilio: str = "", email: str = "", telefono: str = "",
                   domicilio_envio: str = "", localidad_envio: str = "",
                   provincia_envio: str = "", codigo_postal_envio: str = "",
                   notas_envio: str = "") -> Cliente:
    with get_session() as s:
        c = Cliente(razon_social=razon_social, cuit=cuit, condicion_iva=condicion_iva,
                     domicilio=domicilio, email=email, telefono=telefono,
                     domicilio_envio=domicilio_envio, localidad_envio=localidad_envio,
                     provincia_envio=provincia_envio, codigo_postal_envio=codigo_postal_envio,
                     notas_envio=notas_envio)
        s.add(c)
        s.commit()
        s.refresh(c)
        return c


def actualizar_cliente(cliente_id: int, **campos) -> None:
    with get_session() as s:
        c = s.get(Cliente, cliente_id)
        if not c:
            raise ValueError("Cliente no encontrado")
        for k, v in campos.items():
            setattr(c, k, v)
        s.commit()


def obtener_cliente(cliente_id: int) -> Optional[Cliente]:
    with get_session() as s:
        return s.get(Cliente, cliente_id)


def eliminar_cliente(cliente_id: int) -> None:
    with get_session() as s:
        c = s.get(Cliente, cliente_id)
        if not c:
            raise ValueError("Cliente no encontrado")

        tiene_cotizaciones = s.execute(
            select(Cotizacion.id).where(Cotizacion.cliente_id == cliente_id)
        ).first() is not None
        tiene_movimientos = s.execute(
            select(MovimientoCuentaCorriente.id).where(
                MovimientoCuentaCorriente.cliente_id == cliente_id
            )
        ).first() is not None
        tiene_remitos = s.execute(
            select(Remito.id).where(Remito.cliente_id == cliente_id)
        ).first() is not None

        if tiene_cotizaciones or tiene_movimientos or tiene_remitos:
            raise ValueError(
                "No se puede eliminar: el cliente tiene cotizaciones, "
                "movimientos de cuenta corriente o remitos asociados."
            )

        s.delete(c)
        s.commit()


# ---------------------------------------------------------------------------
# Cotizaciones
# ---------------------------------------------------------------------------

def _proximo_numero_cotizacion(s) -> str:
    ultimo = s.execute(
        select(Cotizacion).order_by(Cotizacion.id.desc())
    ).scalars().first()
    siguiente = (ultimo.id + 1) if ultimo else 1
    return f"COT-{siguiente:06d}"


def crear_cotizacion(cliente_id: int, items: list[dict],
                      validez_dias: int = 15, notas: str = "",
                      incluye_iva: bool = False) -> Cotizacion:
    """
    items: [{"producto_id": int, "cantidad": float,
              "precio_unitario": float (opcional, usa precio_venta si falta),
              "descuento_pct": float (opcional)}]
    """
    with get_session() as s:
        numero = _proximo_numero_cotizacion(s)
        cot = Cotizacion(numero=numero, cliente_id=cliente_id,
                          validez_dias=validez_dias, notas=notas,
                          incluye_iva=incluye_iva)
        s.add(cot)
        s.flush()

        for it in items:
            producto = s.get(Producto, it["producto_id"])
            if not producto:
                raise ValueError(f"Producto {it['producto_id']} no existe")
            precio = it.get("precio_unitario", producto.precio_venta)
            item = ItemCotizacion(
                cotizacion_id=cot.id,
                producto_id=producto.id,
                cantidad=it["cantidad"],
                precio_unitario=precio,
                descuento_pct=it.get("descuento_pct", 0.0),
                precio_usd_original=it.get("precio_usd_original"),
                tipo_cambio_usado=it.get("tipo_cambio_usado"),
            )
            s.add(item)

        s.commit()
        s.refresh(cot)
        return cot


def listar_cotizaciones() -> list[Cotizacion]:
    with get_session() as s:
        q = (
            select(Cotizacion)
            .options(
                joinedload(Cotizacion.cliente),
                joinedload(Cotizacion.items).joinedload(ItemCotizacion.producto),
            )
            .order_by(Cotizacion.id.desc())
        )
        return list(s.execute(q).unique().scalars().all())


def listar_cotizaciones_cliente(cliente_id: int) -> list[Cotizacion]:
    with get_session() as s:
        q = (
            select(Cotizacion)
            .where(Cotizacion.cliente_id == cliente_id)
            .options(joinedload(Cotizacion.items).joinedload(ItemCotizacion.producto))
            .order_by(Cotizacion.id.desc())
        )
        return list(s.execute(q).unique().scalars().all())


def obtener_cotizacion(cotizacion_id: int) -> Optional[Cotizacion]:
    with get_session() as s:
        q = (
            select(Cotizacion)
            .where(Cotizacion.id == cotizacion_id)
            .options(
                joinedload(Cotizacion.cliente),
                joinedload(Cotizacion.items).joinedload(ItemCotizacion.producto),
            )
        )
        return s.execute(q).unique().scalars().first()


def actualizar_cotizacion(cotizacion_id: int, cliente_id: int, items: list[dict],
                           validez_dias: Optional[int] = None,
                           notas: Optional[str] = None,
                           incluye_iva: Optional[bool] = None) -> Cotizacion:
    """Reemplaza cliente e ítems de una cotización existente (para corregir errores)."""
    with get_session() as s:
        cot = s.get(Cotizacion, cotizacion_id, options=[joinedload(Cotizacion.items)])
        if not cot:
            raise ValueError("Cotización no encontrada")
        if cot.estado == "Facturada":
            raise ValueError(
                "Esta cotización ya fue facturada y no se puede editar. "
                "Cancelala y creá una nueva si necesitás corregir algo."
            )
        if cot.stock_descontado:
            raise ValueError(
                "Esta cotización está aceptada (el stock ya se descontó). "
                "Revertí la aceptación para poder editarla."
            )

        cot.cliente_id = cliente_id
        if validez_dias is not None:
            cot.validez_dias = validez_dias
        if notas is not None:
            cot.notas = notas
        if incluye_iva is not None:
            cot.incluye_iva = incluye_iva

        # Reemplaza los ítems por completo (cascade "delete-orphan" limpia los viejos)
        cot.items.clear()
        s.flush()
        for it in items:
            producto = s.get(Producto, it["producto_id"])
            if not producto:
                raise ValueError(f"Producto {it['producto_id']} no existe")
            precio = it.get("precio_unitario", producto.precio_venta)
            cot.items.append(ItemCotizacion(
                producto_id=producto.id,
                cantidad=it["cantidad"],
                precio_unitario=precio,
                descuento_pct=it.get("descuento_pct", 0.0),
                precio_usd_original=it.get("precio_usd_original"),
                tipo_cambio_usado=it.get("tipo_cambio_usado"),
            ))

        s.commit()
        s.refresh(cot)
        return cot


def eliminar_cotizacion(cotizacion_id: int) -> None:
    with get_session() as s:
        cot = s.get(Cotizacion, cotizacion_id)
        if not cot:
            raise ValueError("Cotización no encontrada")

        tiene_factura = s.execute(
            select(Factura.id).where(Factura.cotizacion_id == cotizacion_id)
        ).first() is not None
        tiene_remitos = s.execute(
            select(Remito.id).where(Remito.cotizacion_id == cotizacion_id)
        ).first() is not None

        if cot.stock_descontado:
            raise ValueError(
                "No se puede eliminar: está aceptada y ya descontó stock. "
                "Revertí la aceptación primero."
            )

        if tiene_factura or tiene_remitos:
            raise ValueError(
                "No se puede eliminar: ya tiene una factura o un remito generado. "
                "Podés cambiar su estado a 'Cancelada' en su lugar."
            )

        s.delete(cot)
        s.commit()


def cambiar_estado_cotizacion(cotizacion_id: int, nuevo_estado: str) -> None:
    with get_session() as s:
        cot = s.get(Cotizacion, cotizacion_id)
        if not cot:
            raise ValueError("Cotización no encontrada")
        cot.estado = nuevo_estado
        s.commit()


# ---------------------------------------------------------------------------
# Facturación (registro local; la emisión contra ARCA la hace app/afip)
# ---------------------------------------------------------------------------

def _tiene_factura(s, cotizacion_id: int) -> bool:
    return s.execute(
        select(Factura.id).where(Factura.cotizacion_id == cotizacion_id)
    ).first() is not None


def _verificar_stock(cot: Cotizacion, accion: str) -> None:
    """Verifica que alcance el stock de TODOS los ítems antes de tocar nada."""
    for item in cot.items:
        if item.cantidad > item.producto.stock_actual:
            raise ValueError(
                f"Stock insuficiente de {item.producto.codigo} para {accion} "
                f"(disponible: {item.producto.stock_actual:g}, "
                f"requerido: {item.cantidad:g})."
            )


def _descontar_stock(s, cot: Cotizacion, motivo: str) -> None:
    for item in cot.items:
        item.producto.stock_actual -= item.cantidad
        s.add(MovimientoStock(
            producto_id=item.producto_id, tipo="salida",
            cantidad=item.cantidad, motivo=motivo,
        ))
    cot.stock_descontado = True


def aceptar_cotizacion(cotizacion_id: int) -> None:
    """Acepta la cotización (sin facturar) y descuenta el stock una sola vez."""
    with get_session() as s:
        cot = s.get(Cotizacion, cotizacion_id,
                     options=[joinedload(Cotizacion.items).joinedload(ItemCotizacion.producto)])
        if not cot:
            raise ValueError("Cotización no encontrada")
        if cot.estado == "Facturada" or _tiene_factura(s, cot.id):
            raise ValueError("Esta cotización ya está facturada.")
        if cot.estado == "Cancelada":
            raise ValueError("Esta cotización está cancelada.")
        if cot.stock_descontado or cot.estado == "Aceptada":
            raise ValueError("Esta cotización ya fue aceptada (el stock ya se descontó).")
        if not cot.items:
            raise ValueError("La cotización no tiene ítems.")

        _verificar_stock(cot, "aceptar")
        _descontar_stock(s, cot, f"Cotización aceptada {cot.numero}")
        cot.estado = "Aceptada"
        s.commit()


def revertir_aceptacion(cotizacion_id: int) -> None:
    """Deshace una aceptación: devuelve el stock y vuelve la cotización a Borrador."""
    with get_session() as s:
        cot = s.get(Cotizacion, cotizacion_id,
                     options=[joinedload(Cotizacion.items).joinedload(ItemCotizacion.producto)])
        if not cot:
            raise ValueError("Cotización no encontrada")
        if cot.estado == "Facturada" or _tiene_factura(s, cot.id):
            raise ValueError("Ya está facturada: no se puede revertir la aceptación.")
        if cot.estado != "Aceptada" or not cot.stock_descontado:
            raise ValueError("Esta cotización no está aceptada.")

        for item in cot.items:
            item.producto.stock_actual += item.cantidad
            s.add(MovimientoStock(
                producto_id=item.producto_id, tipo="entrada",
                cantidad=item.cantidad,
                motivo=f"Aceptación revertida {cot.numero}",
            ))
        cot.stock_descontado = False
        cot.estado = "Borrador"
        s.commit()


def crear_factura_pendiente(cotizacion_id: int, tipo_comprobante: str,
                             punto_venta: int = 1) -> Factura:
    with get_session() as s:
        cot = s.get(Cotizacion, cotizacion_id,
                     options=[joinedload(Cotizacion.items).joinedload(ItemCotizacion.producto)])
        if not cot:
            raise ValueError("Cotización no encontrada")

        if cot.estado == "Facturada" or _tiene_factura(s, cot.id):
            raise ValueError("Esta cotización ya tiene una factura.")
        if cot.estado == "Cancelada":
            raise ValueError("Esta cotización está cancelada y no se puede facturar.")

        # Si ya se aceptó (y por eso ya se descontó el stock), no se vuelve
        # a descontar. Si no, se verifica y descuenta ahora.
        if not cot.stock_descontado:
            _verificar_stock(cot, "facturar")

        total = cot.total
        fac = Factura(
            cotizacion_id=cot.id,
            tipo_comprobante=tipo_comprobante,
            punto_venta=punto_venta,
            importe_total=total,
            estado="Pendiente",
        )
        s.add(fac)
        cot.estado = "Facturada"

        if not cot.stock_descontado:
            _descontar_stock(
                s, cot, f"Factura {tipo_comprobante} — Cotización {cot.numero}"
            )

        # Genera automáticamente el "debe" en la cuenta corriente del cliente
        movimiento = MovimientoCuentaCorriente(
            cliente_id=cot.cliente_id,
            tipo="debe",
            concepto=f"Factura {tipo_comprobante} — Cotización {cot.numero}",
            importe=total,
        )
        s.add(movimiento)

        s.commit()
        s.refresh(fac)
        return fac


def marcar_factura_emitida(factura_id: int, numero: int, cae: str,
                            cae_vencimiento: dt.date) -> None:
    with get_session() as s:
        fac = s.get(Factura, factura_id)
        if not fac:
            raise ValueError("Factura no encontrada")
        fac.numero = numero
        fac.cae = cae
        fac.cae_vencimiento = cae_vencimiento
        fac.fecha_emision = dt.datetime.now()
        fac.estado = "Emitida"
        s.commit()


def marcar_factura_error(factura_id: int, detalle: str) -> None:
    with get_session() as s:
        fac = s.get(Factura, factura_id)
        if not fac:
            raise ValueError("Factura no encontrada")
        fac.estado = "Error"
        fac.error_detalle = detalle
        s.commit()


# ---------------------------------------------------------------------------
# Cuenta corriente (debe / haber por cliente)
# ---------------------------------------------------------------------------

def listar_movimientos_cliente(cliente_id: int) -> list[MovimientoCuentaCorriente]:
    with get_session() as s:
        q = (
            select(MovimientoCuentaCorriente)
            .where(MovimientoCuentaCorriente.cliente_id == cliente_id)
            .order_by(MovimientoCuentaCorriente.fecha.desc())
        )
        return list(s.execute(q).scalars().all())


def saldo_cliente(cliente_id: int) -> float:
    movimientos = listar_movimientos_cliente(cliente_id)
    return sum(m.importe if m.tipo == "debe" else -m.importe for m in movimientos)


def registrar_cargo(cliente_id: int, importe: float, concepto: str = "Cargo manual") -> MovimientoCuentaCorriente:
    with get_session() as s:
        mov = MovimientoCuentaCorriente(
            cliente_id=cliente_id, tipo="debe", concepto=concepto, importe=importe,
        )
        s.add(mov)
        s.commit()
        s.refresh(mov)
        return mov


def registrar_pago(cliente_id: int, importe: float, medio_pago: str = "Efectivo",
                    concepto: str = "Pago recibido") -> MovimientoCuentaCorriente:
    with get_session() as s:
        mov = MovimientoCuentaCorriente(
            cliente_id=cliente_id, tipo="haber", concepto=concepto,
            importe=importe, medio_pago=medio_pago,
        )
        s.add(mov)
        s.commit()
        s.refresh(mov)
        return mov


def obtener_movimiento_cuenta(movimiento_id: int) -> Optional[MovimientoCuentaCorriente]:
    with get_session() as s:
        return s.get(MovimientoCuentaCorriente, movimiento_id)


def actualizar_movimiento_cuenta(movimiento_id: int, **campos) -> None:
    """Corrige un movimiento de cuenta corriente ya cargado (por si hubo un error)."""
    with get_session() as s:
        mov = s.get(MovimientoCuentaCorriente, movimiento_id)
        if not mov:
            raise ValueError("Movimiento no encontrado")
        for k, v in campos.items():
            setattr(mov, k, v)
        s.commit()


def eliminar_movimiento_cuenta(movimiento_id: int) -> None:
    with get_session() as s:
        mov = s.get(MovimientoCuentaCorriente, movimiento_id)
        if not mov:
            raise ValueError("Movimiento no encontrado")
        s.delete(mov)
        s.commit()


# ---------------------------------------------------------------------------
# Remitos
# ---------------------------------------------------------------------------

def _proximo_numero_remito(s) -> str:
    ultimo = s.execute(
        select(Remito).order_by(Remito.id.desc())
    ).scalars().first()
    siguiente = (ultimo.id + 1) if ultimo else 1
    return f"REM-{siguiente:06d}"


def crear_remito_desde_cotizacion(cotizacion_id: int, domicilio_entrega: str = "",
                                   observaciones: str = "", orden_compra: str = "",
                                   expreso: str = "", numero_formulario: str = "") -> Remito:
    with get_session() as s:
        cot = s.get(Cotizacion, cotizacion_id,
                     options=[joinedload(Cotizacion.items)])
        if not cot:
            raise ValueError("Cotización no encontrada")

        numero = _proximo_numero_remito(s)
        remito = Remito(
            numero=numero,
            cliente_id=cot.cliente_id,
            cotizacion_id=cot.id,
            domicilio_entrega=domicilio_entrega,
            observaciones=observaciones,
            orden_compra=orden_compra,
            expreso=expreso,
            numero_formulario=numero_formulario,
        )
        s.add(remito)
        s.flush()

        for item in cot.items:
            s.add(ItemRemito(
                remito_id=remito.id,
                producto_id=item.producto_id,
                cantidad=item.cantidad,
            ))

        s.commit()
        s.refresh(remito)
        return remito


def listar_remitos_cliente(cliente_id: int) -> list[Remito]:
    with get_session() as s:
        q = (
            select(Remito)
            .where(Remito.cliente_id == cliente_id)
            .options(joinedload(Remito.items).joinedload(ItemRemito.producto))
            .order_by(Remito.id.desc())
        )
        return list(s.execute(q).unique().scalars().all())


def obtener_remito(remito_id: int) -> Optional[Remito]:
    with get_session() as s:
        q = (
            select(Remito)
            .where(Remito.id == remito_id)
            .options(
                joinedload(Remito.cliente),
                joinedload(Remito.items).joinedload(ItemRemito.producto),
            )
        )
        return s.execute(q).unique().scalars().first()


def cambiar_estado_remito(remito_id: int, nuevo_estado: str) -> None:
    with get_session() as s:
        remito = s.get(Remito, remito_id)
        if not remito:
            raise ValueError("Remito no encontrado")
        remito.estado = nuevo_estado
        s.commit()


# ---------------------------------------------------------------------------
# Cotización del dólar (caché diaria)
# ---------------------------------------------------------------------------

def _inicio_del_dia(fecha: dt.date) -> dt.datetime:
    return dt.datetime.combine(fecha, dt.time.min)


def obtener_valor_dolar_cacheado(fecha: Optional[dt.date] = None) -> Optional[ValorDolar]:
    fecha = fecha or dt.date.today()
    with get_session() as s:
        return s.execute(
            select(ValorDolar).where(ValorDolar.fecha == _inicio_del_dia(fecha))
        ).scalars().first()


def obtener_ultimo_valor_dolar() -> Optional[ValorDolar]:
    with get_session() as s:
        return s.execute(
            select(ValorDolar).order_by(ValorDolar.fecha.desc())
        ).scalars().first()


def guardar_valor_dolar(compra: float, venta: float, fuente: str = "BNA",
                         fecha: Optional[dt.date] = None) -> ValorDolar:
    fecha = fecha or dt.date.today()
    with get_session() as s:
        existente = s.execute(
            select(ValorDolar).where(ValorDolar.fecha == _inicio_del_dia(fecha))
        ).scalars().first()
        if existente:
            existente.compra = compra
            existente.venta = venta
            existente.fuente = fuente
            existente.obtenido_en = dt.datetime.now()
            s.commit()
            s.refresh(existente)
            return existente

        nuevo = ValorDolar(
            fecha=_inicio_del_dia(fecha), compra=compra, venta=venta, fuente=fuente,
        )
        s.add(nuevo)
        s.commit()
        s.refresh(nuevo)
        return nuevo


# ---------------------------------------------------------------------------
# Proveedores (independientes de los clientes: no aparecen en cotizaciones)
# ---------------------------------------------------------------------------

def listar_proveedores() -> list[Proveedor]:
    with get_session() as s:
        q = select(Proveedor).where(Proveedor.activo.is_(True)).order_by(Proveedor.razon_social)
        return list(s.execute(q).scalars().all())


def obtener_proveedor(proveedor_id: int) -> Optional[Proveedor]:
    with get_session() as s:
        return s.get(Proveedor, proveedor_id)


def crear_proveedor(razon_social: str, cuit: str = "", condicion_iva: str = "Responsable Inscripto",
                    domicilio: str = "", email: str = "", telefono: str = "",
                    notas: str = "") -> Proveedor:
    with get_session() as s:
        p = Proveedor(razon_social=razon_social, cuit=cuit, condicion_iva=condicion_iva,
                      domicilio=domicilio, email=email, telefono=telefono, notas=notas)
        s.add(p)
        s.commit()
        s.refresh(p)
        return p


def actualizar_proveedor(proveedor_id: int, **campos) -> None:
    with get_session() as s:
        p = s.get(Proveedor, proveedor_id)
        if not p:
            raise ValueError("Proveedor no encontrado")
        for k, v in campos.items():
            setattr(p, k, v)
        s.commit()


def eliminar_proveedor(proveedor_id: int) -> None:
    """Sin facturas ni movimientos se borra; si tiene historial solo se oculta."""
    with get_session() as s:
        p = s.get(Proveedor, proveedor_id)
        if not p:
            raise ValueError("Proveedor no encontrado")
        tiene = s.execute(select(FacturaProveedor.id).where(FacturaProveedor.proveedor_id == proveedor_id)).first() \
            or s.execute(select(MovimientoCuentaProveedor.id).where(
                MovimientoCuentaProveedor.proveedor_id == proveedor_id)).first()
        if tiene:
            p.activo = False
        else:
            s.delete(p)
        s.commit()


def buscar_proveedor_por_cuit(cuits: list[str]) -> Optional[Proveedor]:
    limpios = {"".join(ch for ch in c if ch.isdigit()) for c in cuits}
    for p in listar_proveedores():
        if p.cuit and "".join(ch for ch in p.cuit if ch.isdigit()) in limpios:
            return p
    return None


def listar_movimientos_proveedor(proveedor_id: int) -> list[MovimientoCuentaProveedor]:
    with get_session() as s:
        q = (select(MovimientoCuentaProveedor)
             .where(MovimientoCuentaProveedor.proveedor_id == proveedor_id)
             .order_by(MovimientoCuentaProveedor.fecha.desc(), MovimientoCuentaProveedor.id.desc()))
        return list(s.execute(q).scalars().all())


def saldo_proveedor(proveedor_id: int) -> float:
    """Positivo = le debemos al proveedor. Negativo = tenemos saldo a favor."""
    return sum(m.importe if m.tipo == "debe" else -m.importe
               for m in listar_movimientos_proveedor(proveedor_id))


def registrar_movimiento_proveedor(proveedor_id: int, tipo: str, importe: float,
                                   concepto: str, medio_pago: str = "") -> MovimientoCuentaProveedor:
    if tipo not in ("debe", "haber"):
        raise ValueError("Tipo inválido")
    with get_session() as s:
        m = MovimientoCuentaProveedor(proveedor_id=proveedor_id, tipo=tipo, importe=importe,
                                      concepto=concepto, medio_pago=medio_pago or None)
        s.add(m)
        s.commit()
        s.refresh(m)
        return m


def actualizar_movimiento_proveedor(movimiento_id: int, **campos) -> None:
    with get_session() as s:
        m = s.get(MovimientoCuentaProveedor, movimiento_id)
        if not m:
            raise ValueError("Movimiento no encontrado")
        for k, v in campos.items():
            setattr(m, k, v)
        s.commit()


def eliminar_movimiento_proveedor(movimiento_id: int) -> None:
    with get_session() as s:
        m = s.get(MovimientoCuentaProveedor, movimiento_id)
        if not m:
            raise ValueError("Movimiento no encontrado")
        if m.factura_id:
            raise ValueError("Este movimiento pertenece a una factura cargada. "
                             "Eliminá la factura desde la pestaña Facturas.")
        s.delete(m)
        s.commit()


def alias_de_proveedor(proveedor_id: int) -> dict:
    with get_session() as s:
        filas = s.execute(select(AliasProductoProveedor)
                          .where(AliasProductoProveedor.proveedor_id == proveedor_id)).scalars().all()
        return {a.texto: a.producto_id for a in filas}


def _codigos_existentes(s) -> set:
    return set(s.execute(select(Producto.codigo)).scalars().all())


def crear_factura_proveedor(proveedor_id: int, numero: str, fecha: dt.date, total: float,
                            items: list[dict], observaciones: str = "",
                            archivo: str = "") -> dict:
    """
    items: [{descripcion, cantidad, precio_unitario,
             accion: "existente" | "nuevo" | "omitir", producto_id (si existente),
             descripcion_norm (para recordar el alias)}]
    Suma el stock de lo que corresponda, registra la deuda (debe) con el proveedor
    y recuerda las asociaciones descripción -> producto. NO modifica el costo de
    productos existentes; los productos nuevos nacen con el costo de la factura.
    Devuelve un resumen {sumados, creados, omitidos, factura_id}.
    """
    resumen = {"sumados": 0, "creados": 0, "omitidos": 0, "factura_id": None}
    with get_session() as s:
        prov = s.get(Proveedor, proveedor_id)
        if not prov:
            raise ValueError("Proveedor no encontrado")
        factura = FacturaProveedor(
            proveedor_id=proveedor_id, numero=numero,
            fecha=dt.datetime.combine(fecha, dt.time.min), total=total,
            observaciones=observaciones, archivo=archivo or None, stock_aplicado=True)
        s.add(factura)
        s.flush()

        codigos = _codigos_existentes(s)
        proximo = 0
        motivo = f"Factura {numero or factura.id} - {prov.razon_social}"
        for it in items:
            accion = it.get("accion", "omitir")
            cant = float(it.get("cantidad") or 0)
            producto = None
            if accion == "existente" and it.get("producto_id"):
                producto = s.get(Producto, it["producto_id"])
            elif accion == "nuevo":
                while True:
                    proximo += 1
                    codigo = f"SIN-CODIGO-{proximo:03d}"
                    if codigo not in codigos:
                        break
                codigos.add(codigo)
                producto = Producto(
                    codigo=codigo, descripcion=it["descripcion"],
                    precio_costo=float(it.get("precio_unitario") or 0), precio_venta=0.0,
                    stock_actual=0.0)
                s.add(producto)
                s.flush()
                resumen["creados"] += 1

            sumado = 0.0
            if producto is not None and cant > 0:
                producto.stock_actual = (producto.stock_actual or 0) + cant
                s.add(MovimientoStock(producto_id=producto.id, tipo="entrada",
                                      cantidad=cant, motivo=motivo))
                sumado = cant
                resumen["sumados"] += 1
                clave = it.get("descripcion_norm")
                if clave:
                    ya = s.execute(select(AliasProductoProveedor).where(
                        AliasProductoProveedor.proveedor_id == proveedor_id,
                        AliasProductoProveedor.texto == clave)).scalars().first()
                    if ya:
                        ya.producto_id = producto.id
                    else:
                        s.add(AliasProductoProveedor(proveedor_id=proveedor_id, texto=clave,
                                                     producto_id=producto.id))
            else:
                resumen["omitidos"] += 1

            s.add(ItemFacturaProveedor(
                factura_id=factura.id, producto_id=producto.id if producto is not None else None,
                descripcion=it.get("descripcion"), cantidad=cant,
                precio_unitario=float(it.get("precio_unitario") or 0), stock_sumado=sumado))

        s.add(MovimientoCuentaProveedor(
            proveedor_id=proveedor_id, tipo="debe", importe=total,
            concepto=f"Factura {numero or factura.id}", factura_id=factura.id,
            fecha=dt.datetime.combine(fecha, dt.time.min)))
        s.commit()
        resumen["factura_id"] = factura.id
    return resumen


def listar_facturas_proveedor(proveedor_id: int) -> list[FacturaProveedor]:
    with get_session() as s:
        q = (select(FacturaProveedor).where(FacturaProveedor.proveedor_id == proveedor_id)
             .options(joinedload(FacturaProveedor.items).joinedload(ItemFacturaProveedor.producto))
             .order_by(FacturaProveedor.fecha.desc(), FacturaProveedor.id.desc()))
        return list(s.execute(q).unique().scalars().all())


def eliminar_factura_proveedor(factura_id: int, revertir_stock: bool = True) -> None:
    """Borra la factura y su deuda; opcionalmente resta del stock lo que había sumado."""
    with get_session() as s:
        f = s.execute(select(FacturaProveedor).where(FacturaProveedor.id == factura_id)
                      .options(joinedload(FacturaProveedor.items))).unique().scalars().first()
        if not f:
            raise ValueError("Factura no encontrada")
        if revertir_stock:
            for it in f.items:
                if it.producto_id and (it.stock_sumado or 0) > 0:
                    p = s.get(Producto, it.producto_id)
                    if p:
                        quitar = min(it.stock_sumado, p.stock_actual or 0)
                        p.stock_actual = (p.stock_actual or 0) - quitar
                        s.add(MovimientoStock(producto_id=p.id, tipo="salida", cantidad=quitar,
                                              motivo=f"Se eliminó la factura {f.numero or f.id}"))
        for m in s.execute(select(MovimientoCuentaProveedor)
                           .where(MovimientoCuentaProveedor.factura_id == factura_id)).scalars().all():
            s.delete(m)
        s.delete(f)
        s.commit()


# ---------------------------------------------------------------------------
# Balance general
# ---------------------------------------------------------------------------

def balance_general(desde: Optional[dt.date] = None, hasta: Optional[dt.date] = None) -> dict:
    """
    Resumen entre lo que entra y lo que sale en un período (desde/hasta inclusive; None = sin límite).
      entradas  = cobros a clientes (haber de la cuenta corriente de clientes)
      salidas   = pagos a proveedores (haber de la cuenta corriente de proveedores)
      facturado = lo cargado al debe de clientes; comprado = lo cargado al debe de proveedores
      por_cobrar / por_pagar = saldos pendientes AL DÍA DE HOY (no dependen del período)
      movimientos = lista de cobros y pagos del período, más nuevos primero
    """
    ini = dt.datetime.combine(desde, dt.time.min) if desde else None
    fin = dt.datetime.combine(hasta, dt.time.max) if hasta else None

    def en_periodo(f):
        return f is not None and (ini is None or f >= ini) and (fin is None or f <= fin)

    with get_session() as s:
        clientes = {c.id: c.razon_social for c in s.execute(select(Cliente)).scalars()}
        provs = {p.id: p.razon_social for p in s.execute(select(Proveedor)).scalars()}
        mov_c = list(s.execute(select(MovimientoCuentaCorriente)).scalars())
        mov_p = list(s.execute(select(MovimientoCuentaProveedor)).scalars())

    res = dict(entradas=0.0, salidas=0.0, facturado=0.0, comprado=0.0,
               por_cobrar=0.0, por_pagar=0.0, movimientos=[], por_medio_entradas={}, por_medio_salidas={})

    saldo_c: dict[int, float] = {}
    for m in mov_c:
        signo = 1 if m.tipo == "debe" else -1
        saldo_c[m.cliente_id] = saldo_c.get(m.cliente_id, 0.0) + signo * (m.importe or 0)
        if not en_periodo(m.fecha):
            continue
        if m.tipo == "haber":
            res["entradas"] += m.importe or 0
            medio = m.medio_pago or "Sin especificar"
            res["por_medio_entradas"][medio] = res["por_medio_entradas"].get(medio, 0.0) + (m.importe or 0)
            res["movimientos"].append(dict(fecha=m.fecha, tipo="Entrada", contraparte=clientes.get(m.cliente_id, "?"),
                                           concepto=m.concepto or "", medio=m.medio_pago or "", importe=m.importe or 0))
        else:
            res["facturado"] += m.importe or 0

    saldo_p: dict[int, float] = {}
    for m in mov_p:
        signo = 1 if m.tipo == "debe" else -1
        saldo_p[m.proveedor_id] = saldo_p.get(m.proveedor_id, 0.0) + signo * (m.importe or 0)
        if not en_periodo(m.fecha):
            continue
        if m.tipo == "haber":
            res["salidas"] += m.importe or 0
            medio = m.medio_pago or "Sin especificar"
            res["por_medio_salidas"][medio] = res["por_medio_salidas"].get(medio, 0.0) + (m.importe or 0)
            res["movimientos"].append(dict(fecha=m.fecha, tipo="Salida", contraparte=provs.get(m.proveedor_id, "?"),
                                           concepto=m.concepto or "", medio=m.medio_pago or "", importe=m.importe or 0))
        else:
            res["comprado"] += m.importe or 0

    res["por_cobrar"] = sum(v for v in saldo_c.values() if v > 0.005)
    res["por_pagar"] = sum(v for v in saldo_p.values() if v > 0.005)
    res["movimientos"].sort(key=lambda x: x["fecha"] or dt.datetime.min, reverse=True)
    return res
