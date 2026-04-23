"""Database initialization utilities for properties service"""
import os
import json
from datetime import date
from uuid import UUID
from sqlmodel import Session, select

from adapters.models.property import Property
from adapters.models.property_image import PropertyImage
from adapters.models.property_review import PropertyReview


# Property IDs (using fixed UUIDs for frontend to use)
RENAISSANCE_ESTATE_ID = UUID("11111111-1111-1111-1111-111111111111")
BEACHFRONT_PENTHOUSE_ID = UUID("22222222-2222-2222-2222-222222222222")
ALPINE_LODGE_ID = UUID("33333333-3333-3333-3333-333333333333")
TROPICAL_VILLA_ID = UUID("44444444-4444-4444-4444-444444444444")


PROPERTIES_DATA = [
    {
        "id": RENAISSANCE_ESTATE_ID,
        "name": "Mansión Renacentista & Viñedo Privado",
        "description": "Experimenta la elegancia atemporal de esta mansión renacentista del siglo XVIII, ubicada en el corazón de un viñedo en funcionamiento con vistas panorámicas justo fuera de Florencia. La villa ha sido meticulosamente restaurada combinando carácter histórico con lujo ultramoderno. Esta propiedad histórica cuenta con 4 dormitorios de lujo con baños privados, cada uno decorado con muebles de época y comodidades modernas.",
        "location": "Fiesole, Florencia",
        "latitude": 43.8047,
        "longitude": 11.2844,
        "price_per_night": 1240.0,
        "currency": "COP",
        "rating": 4.98,
        "review_count": 54,
        "bedrooms": 4,
        "bathrooms": 4.5,
        "max_guests": 12,
        "amenities": [
            "Piscina Infinita Privada",
            "WiFi Fibra de Alta Velocidad",
            "Acceso Viñedo Privado",
            "Cocina Profesional",
            "Estacionamiento con Valet Gratuito",
            "Control Climático",
            "Sistema Domótico Inteligente",
            "Bodega de Vinos"
        ],
        "cancellation_policy": "Cancelación gratuita hasta 7 días antes del check-in. Cancelación al 50% entre 3 y 7 días. Sin reembolso con menos de 3 días.",
        "tax_rate": 0.19,
        "cleaning_fee": 120.0,
        "images": [
            ("1", "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=800&q=80", "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=1920&q=90", "Vista Principal Mansión Renacentista", 0, True),
            ("2", "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=800&q=80", "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=1920&q=90", "Dormitorio", 1, False),
            ("3", "https://images.unsplash.com/photo-1552321554-5fefe8c9ef14?w=800&q=80", "https://images.unsplash.com/photo-1552321554-5fefe8c9ef14?w=1920&q=90", "Baño", 2, False),
            ("4", "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=800&q=80", "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=1920&q=90", "Comedor", 3, False),
            ("5", "https://images.unsplash.com/photo-1493857671505-72967e2e2760?w=800&q=80", "https://images.unsplash.com/photo-1493857671505-72967e2e2760?w=1920&q=90", "Sala de Estar", 4, False),
        ],
        "reviews": [
            ("María González", 5, date(2024, 9, 15), "¡Fue lo mejor de mis vacaciones! Propiedad increíble con atención excepcional a los detalles. ¡Altamente recomendado!"),
            ("Carlos Rodríguez", 5, date(2024, 8, 20), "Ubicación hermosa y servicio excepcional. El anfitrión fue increíblemente atento. ¡Definitivamente volveremos!"),
        ],
    },
    {
        "id": BEACHFRONT_PENTHOUSE_ID,
        "name": "Penthouse Moderno Frente a la Playa",
        "description": "Penthouse contemporáneo impresionante con acceso directo a la playa y vistas panorámicas del océano. Esta propiedad ultramoderna cuenta con ventanas del piso al techo, diseño minimalista y tecnología de última generación. Despierta con el sonido de las olas mientras disfrutas de tu café matutino en la amplia terraza.",
        "location": "Playa Miami, Florida",
        "latitude": 25.7907,
        "longitude": -80.1300,
        "price_per_night": 2150.0,
        "currency": "USD",
        "rating": 4.87,
        "review_count": 42,
        "bedrooms": 3,
        "bathrooms": 3.0,
        "max_guests": 8,
        "amenities": [
            "Acceso Privado a Playa",
            "Vistas Panorámicas 360°",
            "Automatización Hogar Inteligente",
            "Cocina de Chef",
            "Enfriador de Vinos",
            "Sauna y Baño de Vapor",
            "Servicio de Conserjería",
            "Terraza en Azotea"
        ],
        "cancellation_policy": "Cancelación gratuita hasta 14 días antes del check-in. Sin reembolso con menos de 14 días.",
        "tax_rate": 0.13,
        "cleaning_fee": 200.0,
        "images": [
            ("1", "https://images.unsplash.com/photo-1559827260-dc66d52bef19?w=800&q=80", "https://images.unsplash.com/photo-1559827260-dc66d52bef19?w=1920&q=90", "Vista Frente a la Playa", 0, True),
            ("2", "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800&q=80", "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=1920&q=90", "Dormitorio Principal", 1, False),
            ("3", "https://images.unsplash.com/photo-1552321554-5fefe8c9ef14?w=800&q=80", "https://images.unsplash.com/photo-1552321554-5fefe8c9ef14?w=1920&q=90", "Baño Moderno", 2, False),
            ("4", "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=800&q=80", "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=1920&q=90", "Sala de Estar", 3, False),
            ("5", "https://images.unsplash.com/photo-1512453694671-cf5310a1d7f8?w=800&q=80", "https://images.unsplash.com/photo-1512453694671-cf5310a1d7f8?w=1920&q=90", "Vista Terraza", 4, False),
        ],
        "reviews": [
            ("Ana Martínez", 5, date(2024, 9, 10), "¡Lo mejor de mis vacaciones! Propiedad asombrosa con atención increíble. ¡Altamente recomendado!"),
            ("Juan Pérez", 5, date(2024, 8, 5), "Ubicación espectacular y servicio excepcional. El anfitrión se enforzó mucho para hacernos sentir bienvenido. ¡Volveremos!"),
        ],
    },
    {
        "id": ALPINE_LODGE_ID,
        "name": "Refugio Alpino de Montaña",
        "description": "Acogedor refugio de lujo en montaña rodeado de paisaje alpino prístino y picos nevados. Retiro perfecto para senderismo, esquí, o simplemente relajarse junto a la chimenea. Esta propiedad increíble está rodeada de vistas alpinas exuberantes y ofrece acceso directo a actividades de montaña.",
        "location": "Chamonix, Alpes Franceses",
        "latitude": 45.9237,
        "longitude": 6.8694,
        "price_per_night": 890.0,
        "currency": "EUR",
        "rating": 4.92,
        "review_count": 67,
        "bedrooms": 5,
        "bathrooms": 4.0,
        "max_guests": 14,
        "amenities": [
            "Chimenea de Piedra",
            "Vistas a las Montañas",
            "Almacenamiento de Esquís",
            "Sauna Calefactada",
            "Acceso Esquí Salida/Entrada",
            "Sala de Juegos",
            "Bodega de Vinos",
            "Biblioteca"
        ],
        "cancellation_policy": "Cancelación gratuita hasta 21 días antes del check-in. Cancelación al 50% entre 10 y 21 días. Sin reembolso con menos de 10 días.",
        "tax_rate": 0.20,
        "cleaning_fee": 150.0,
        "images": [
            ("1", "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=800&q=80", "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=1920&q=90", "Exterior Refugio Montaña", 0, True),
            ("2", "https://images.unsplash.com/photo-1571508601155-8a95d1df991c?w=800&q=80", "https://images.unsplash.com/photo-1571508601155-8a95d1df991c?w=1920&q=90", "Sala de Estar Acogedora", 1, False),
            ("3", "https://images.unsplash.com/photo-1552321554-5fefe8c9ef14?w=800&q=80", "https://images.unsplash.com/photo-1552321554-5fefe8c9ef14?w=1920&q=90", "Baño de Lujo", 2, False),
            ("4", "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=800&q=80", "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=1920&q=90", "Área de Comedor", 3, False),
            ("5", "https://images.unsplash.com/photo-1511632765486-a01980e01a18?w=800&q=80", "https://images.unsplash.com/photo-1511632765486-a01980e01a18?w=1920&q=90", "Vista a la Montaña", 4, False),
        ],
        "reviews": [
            ("Elena Gómez", 5, date(2024, 7, 10), "¡Retiro montañoso perfecto! Las vistas de la chimenea son absolutamente impresionantes. Perfecto para escapada invernal."),
            ("Diego López", 5, date(2024, 6, 5), "Mejor experiencia esquí entrada/salida que he tenido. El refugio es acogedor y el servicio impecable."),
        ],
    },
    {
        "id": TROPICAL_VILLA_ID,
        "name": "Villa Paraíso Tropical",
        "description": "Villa de playa exótica con acceso directo a playas de arena blanca y aguas turquesas. Esta propiedad increíble está rodeada de exuberantes jardines tropicales, palmeras y flores exóticas. Despierta con los sonidos de la naturaleza y disfruta de la escapada tropical perfecta.",
        "location": "Bora Bora, Polinesia Francesa",
        "latitude": -16.5004,
        "longitude": -151.7415,
        "price_per_night": 1650.0,
        "currency": "USD",
        "rating": 4.99,
        "review_count": 89,
        "bedrooms": 4,
        "bathrooms": 4.0,
        "max_guests": 10,
        "amenities": [
            "Frente a la Playa",
            "Piscina Infinita",
            "Ducha Exterior",
            "Equipo Deportes Acuáticos",
            "Jardines Tropicales",
            "Bar Tiki",
            "Pabellón Aéreo",
            "Acceso Esnórquel"
        ],
        "cancellation_policy": "No reembolsable. Política estricta de cancelación.",
        "tax_rate": 0.0,
        "cleaning_fee": 180.0,
        "images": [
            ("1", "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=800&q=80", "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=1920&q=90", "Playa Tropical", 0, True),
            ("2", "https://images.unsplash.com/photo-1615529162887-a4521ea3dffb?w=800&q=80", "https://images.unsplash.com/photo-1615529162887-a4521ea3dffb?w=1920&q=90", "Bungaló Dormitorio", 1, False),
            ("3", "https://images.unsplash.com/photo-1552321554-5fefe8c9ef14?w=800&q=80", "https://images.unsplash.com/photo-1552321554-5fefe8c9ef14?w=1920&q=90", "Baño Exterior", 2, False),
            ("4", "https://images.unsplash.com/photo-1576610616656-d3aa5d1f4534?w=800&q=80", "https://images.unsplash.com/photo-1576610616656-d3aa5d1f4534?w=1920&q=90", "Piscina Infinita", 3, False),
            ("5", "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=800&q=80", "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=1920&q=90", "Vista Atardecer", 4, False),
        ],
        "reviews": [
            ("Sofía Rodríguez", 5, date(2024, 9, 1), "¡Paraíso encontrado! Esta villa superó todas mis expectativas. ¡El acceso a la playa es increíble!"),
            ("Miguel Fernández", 5, date(2024, 8, 1), "¡Mejores vacaciones de mi vida! El entorno tropical y comodidades son de clase mundial. ¡Definitivamente volvemos!"),
        ],
    },
]


def seed_properties_if_empty(session: Session) -> None:
    """Seed database with sample properties if empty"""
    # Check if properties already exist
    existing = session.exec(select(Property).limit(1)).first()
    if existing:
        return

    try:
        # Add all properties
        for prop_data in PROPERTIES_DATA:
            property_obj = Property(
                id=prop_data["id"],
                name=prop_data["name"],
                description=prop_data["description"],
                location=prop_data["location"],
                latitude=prop_data["latitude"],
                longitude=prop_data["longitude"],
                price_per_night=prop_data["price_per_night"],
                currency=prop_data["currency"],
                rating=prop_data["rating"],
                review_count=prop_data["review_count"],
                bedrooms=prop_data["bedrooms"],
                bathrooms=prop_data["bathrooms"],
                max_guests=prop_data["max_guests"],
                amenities=json.dumps(prop_data["amenities"]),
                cancellation_policy=prop_data["cancellation_policy"],
                tax_rate=prop_data["tax_rate"],
                cleaning_fee=prop_data["cleaning_fee"],
                status=1,
            )
            session.add(property_obj)

        session.commit()

        # Add images
        for prop_data in PROPERTIES_DATA:
            for img_id, url, url_hires, alt_text, position, is_cover in prop_data["images"]:
                image = PropertyImage(
                    property_id=prop_data["id"],
                    url=url,
                    url_hires=url_hires,
                    alt_text=alt_text,
                    position=position,
                    is_cover=is_cover,
                )
                session.add(image)

        session.commit()

        # Add reviews
        for prop_data in PROPERTIES_DATA:
            for author, rating, review_date, comment in prop_data["reviews"]:
                review = PropertyReview(
                    property_id=prop_data["id"],
                    author=author,
                    rating=rating,
                    review_date=review_date,
                    comment=comment,
                    verified_stay=True,
                )
                session.add(review)

        session.commit()

    except Exception as e:
        session.rollback()
        raise
