# envios/cart.py
"""
Carrito de "servicios de envío" usando sesiones de Django.
Permite agrupar múltiples encomiendas antes de generar la orden.
"""

from decimal import Decimal
from django.conf import settings


class CartItem:
    """Representa un item en el carrito (encomienda pendiente de registrar)"""
    def __init__(self, temp_id, codigo, descripcion, peso_kg, remitente_id, 
                 destinatario_id, ruta_id, costo_envio, volumen_cm3=None):
        self.temp_id = temp_id
        self.codigo = codigo
        self.descripcion = descripcion
        self.peso_kg = Decimal(str(peso_kg))
        self.volumen_cm3 = Decimal(str(volumen_cm3)) if volumen_cm3 else None
        self.remitente_id = remitente_id
        self.destinatario_id = destinatario_id
        self.ruta_id = ruta_id
        self.costo_envio = Decimal(str(costo_envio))
    
    def to_dict(self):
        return {
            'temp_id': self.temp_id,
            'codigo': self.codigo,
            'descripcion': self.descripcion,
            'peso_kg': float(self.peso_kg),
            'volumen_cm3': float(self.volumen_cm3) if self.volumen_cm3 else None,
            'remitente_id': self.remitente_id,
            'destinatario_id': self.destinatario_id,
            'ruta_id': self.ruta_id,
            'costo_envio': float(self.costo_envio),
        }
    
    @property
    def peso_display(self):
        return f"{self.peso_kg} kg"
    
    @property
    def costo_display(self):
        return f"S/ {self.costo_envio:.2f}"


class Cart:
    """
    Gestiona el carrito de servicios de envío mediante sesiones Django.
    Equivalente a core/cart.py del PDF pero adaptado para encomiendas.
    """
    
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(settings.CART_SESSION_ID)
        if not cart:
            cart = self.session[settings.CART_SESSION_ID] = {}
        self.cart = cart
    
    def add(self, item_data):
        """
        Añade una encomienda al carrito.
        item_data: dict con datos de la encomienda temporal
        """
        temp_id = item_data['temp_id']
        
        self.cart[temp_id] = {
            'codigo': item_data.get('codigo', ''),
            'descripcion': item_data.get('descripcion', ''),
            'peso_kg': float(item_data.get('peso_kg', 0)),
            'volumen_cm3': float(item_data['volumen_cm3']) if item_data.get('volumen_cm3') else None,
            'remitente_id': item_data.get('remitente_id'),
            'destinatario_id': item_data.get('destinatario_id'),
            'ruta_id': item_data.get('ruta_id'),
            'costo_envio': float(item_data.get('costo_envio', 0)),
        }
        self.save()
    
    def remove(self, temp_id):
        """Elimina una encomienda del carrito"""
        if temp_id in self.cart:
            del self.cart[temp_id]
            self.save()
    
    def get_items(self):
        """Retorna lista de CartItem"""
        items = []
        for temp_id, data in self.cart.items():
            item = CartItem(
                temp_id=temp_id,
                codigo=data['codigo'],
                descripcion=data['descripcion'],
                peso_kg=data['peso_kg'],
                remitente_id=data['remitente_id'],
                destinatario_id=data['destinatario_id'],
                ruta_id=data['ruta_id'],
                costo_envio=data['costo_envio'],
                volumen_cm3=data.get('volumen_cm3'),
            )
            items.append(item)
        return items
    
    def __iter__(self):
        """Permite iterar sobre los items del carrito"""
        for item in self.get_items():
            yield item
    
    def __len__(self):
        """Cantidad de encomiendas en el carrito"""
        return len(self.cart)
    
    @property
    def total_peso(self):
        """Peso total de todas las encomiendas"""
        return sum(Decimal(str(item['peso_kg'])) for item in self.cart.values())
    
    @property
    def total_costo(self):
        """Costo total del envío"""
        return sum(Decimal(str(item['costo_envio'])) for item in self.cart.values())
    
    @property
    def total_items(self):
        return len(self)
    
    def clear(self):
        """Vaciar carrito"""
        del self.session[settings.CART_SESSION_ID]
        self.save()
    
    def save(self):
        """Marca la sesión como modificada para guardar"""
        self.session.modified = True