"""Conversores integrados.

Cada módulo de este paquete se importa durante ``registry.discover()`` y sus
conversores se auto-registran con el decorador ``@register``. Los módulos solo
pueden importar stdlib a nivel de módulo; las dependencias opcionales se
importan dentro de ``convert``.
"""
