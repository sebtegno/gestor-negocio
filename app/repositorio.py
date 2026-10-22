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
