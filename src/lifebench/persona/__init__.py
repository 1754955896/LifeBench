"""Persona synthesis public API with lazy imports."""

__all__ = ["PersonaGenerator", "PersonaAddressService"]


def __getattr__(name):
    if name == "PersonaGenerator":
        from .persona_gen import PersonaGenerator
        return PersonaGenerator
    if name == "PersonaAddressService":
        from .address_generation import PersonaAddressService
        return PersonaAddressService
    raise AttributeError(name)
