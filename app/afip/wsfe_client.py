"""
Integración con el webservice de Facturación Electrónica de ARCA (WSFEv1).

Requiere:
  - Un certificado digital (.crt) y clave privada (.key) generados en
    ARCA > "Administrador de Certificados Digitales", asociados a tu CUIT
    y con el webservice "wsfe" autorizado.
  - El paquete `pyafipws` (o alternativamente se puede implementar con
    `zeep` a mano; acá se deja la interfaz lista para pyafipws porque
    ya resuelve el login (WSAA) y el armado del ticket de acceso).

IMPORTANTE: esta app NO se conecta a internet desde este entorno de
desarrollo (sandbox sin red), así que este módulo no pudo probarse contra
los servidores reales de ARCA. Antes de usarlo en producción:
  1. Colocá tus archivos certificado.crt y clave.key en la carpeta certs/.
  2. Probá primero contra el ambiente de HOMOLOGACIÓN (testing) de ARCA,
     no contra producción.
  3. Revisá que el número de punto de venta y CUIT coincidan con los
     habilitados en tu cuenta ARCA.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

from ..rutas import carpeta_certs

CERTS_DIR = carpeta_certs()

# URLs de los servicios (homologación = testing, producción = real)
WSAA_URL_HOMO = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms"
WSAA_URL_PROD = "https://wsaa.afip.gov.ar/ws/services/LoginCms"
WSFE_URL_HOMO = "https://wswhomo.afip.gov.ar/wsfev1/service.asmx"
WSFE_URL_PROD = "https://servicios1.afip.gov.ar/wsfev1/service.asmx"

# Códigos de tipo de comprobante que usa ARCA
TIPO_COMPROBANTE = {
    "A": 1,   # Factura A
    "B": 6,   # Factura B
}

# Códigos de condición frente al IVA del receptor (RG 5616)
CONDICION_IVA_RECEPTOR = {
    "Responsable Inscripto": 1,
    "Monotributo": 6,
    "Exento": 4,
    "Consumidor Final": 5,
}


@dataclass
class DatosFactura:
    cuit_emisor: str
    punto_venta: int
    tipo_comprobante: str  # "A" | "B"
    concepto: int  # 1=Productos, 2=Servicios, 3=Productos y Servicios
    doc_tipo_receptor: int  # 80=CUIT, 96=DNI, 99=Consumidor Final sin doc
    doc_nro_receptor: str
    condicion_iva_receptor: str
    importe_neto: float
    importe_iva: float
    importe_total: float
    fecha: dt.date


@dataclass
class ResultadoAutorizacion:
    aprobado: bool
    cae: str | None
    cae_vencimiento: dt.date | None
    numero_comprobante: int | None
    observaciones: str | None


class ClienteWSFE:
    """
    Envoltorio sobre pyafipws.WSFEv1.

    Uso típico:
        cliente = ClienteWSFE(cuit="20XXXXXXXX3", produccion=False)
        cliente.autenticar()
        resultado = cliente.autorizar_factura(datos_factura)
    """

    def __init__(self, cuit: str, produccion: bool = False):
        self.cuit = cuit
        self.produccion = produccion
        self._wsfe = None  # instancia real de pyafipws.WSFEv1.WSFEv1()

    def autenticar(self) -> None:
        """
        Genera el Ticket de Acceso (TA) contra WSAA usando el certificado
        y la clave privada, y lo pasa a la instancia de WSFEv1.

        Implementación pendiente de conectar con pyafipws:

            from pyafipws.wsaa import WSAA
            from pyafipws.wsfev1 import WSFEv1

            wsaa = WSAA()
            cert = str(CERTS_DIR / "certificado.crt")
            key = str(CERTS_DIR / "clave.key")
            wsaa_url = WSAA_URL_PROD if self.produccion else WSAA_URL_HOMO
            ta = wsaa.Autenticar("wsfe", cert, key, wsaa_url)

            self._wsfe = WSFEv1()
            self._wsfe.Cuit = self.cuit
            self._wsfe.SetTicketAcceso(ta)
            self._wsfe.Conectar(wsdl=WSFE_URL_PROD if self.produccion else WSFE_URL_HOMO)
        """
        raise NotImplementedError(
            "Falta instalar pyafipws y colocar los certificados en certs/. "
            "Ver docstring de este método para el código de conexión."
        )

    def proximo_numero_comprobante(self, punto_venta: int, tipo_comprobante: str) -> int:
        """Consulta a ARCA cuál es el último comprobante autorizado y devuelve el siguiente."""
        if self._wsfe is None:
            raise RuntimeError("Llamá a autenticar() primero")
        tipo_cbte = TIPO_COMPROBANTE[tipo_comprobante]
        ultimo = self._wsfe.CompUltimoAutorizado(punto_venta, tipo_cbte)
        return int(ultimo) + 1

    def autorizar_factura(self, datos: DatosFactura) -> ResultadoAutorizacion:
        """
        Arma y envía el comprobante a ARCA, devuelve el CAE si fue aprobado.
        """
        if self._wsfe is None:
            raise RuntimeError("Llamá a autenticar() primero")

        numero = self.proximo_numero_comprobante(datos.punto_venta, datos.tipo_comprobante)
        tipo_cbte = TIPO_COMPROBANTE[datos.tipo_comprobante]

        self._wsfe.CrearFactura(
            concepto=datos.concepto,
            tipo_doc=datos.doc_tipo_receptor,
            nro_doc=datos.doc_nro_receptor,
            tipo_cbte=tipo_cbte,
            punto_vta=datos.punto_venta,
            cbt_desde=numero,
            cbt_hasta=numero,
            imp_total=datos.importe_total,
            imp_neto=datos.importe_neto,
            imp_iva=datos.importe_iva,
            fecha_cbte=datos.fecha.strftime("%Y%m%d"),
        )
        # Alícuotas de IVA (ajustar según composición real de la factura)
        self._wsfe.AgregarIva(id_iva=5, base_imp=datos.importe_neto, importe=datos.importe_iva)

        self._wsfe.CAESolicitar()

        if self._wsfe.Resultado == "A":  # Aprobado
            return ResultadoAutorizacion(
                aprobado=True,
                cae=self._wsfe.CAE,
                cae_vencimiento=dt.datetime.strptime(
                    self._wsfe.Vencimiento, "%Y%m%d"
                ).date(),
                numero_comprobante=numero,
                observaciones=self._wsfe.Obs,
            )
        return ResultadoAutorizacion(
            aprobado=False, cae=None, cae_vencimiento=None,
            numero_comprobante=None, observaciones=self._wsfe.ErrMsg,
        )
