"""Database initialization utilities for properties service."""
import json
import math
from datetime import date
from uuid import UUID

from sqlmodel import Session, select

from adapters.models.property import Property
from adapters.models.property_cancellation_policy import PropertyCancellationPolicy
from adapters.models.property_image import PropertyImage
from adapters.models.property_review import PropertyReview
from core.config import settings


RENAISSANCE_ESTATE_ID = UUID("11111111-1111-1111-1111-111111111111")
BEACHFRONT_PENTHOUSE_ID = UUID("22222222-2222-2222-2222-222222222222")
ALPINE_LODGE_ID = UUID("33333333-3333-3333-3333-333333333333")
TROPICAL_VILLA_ID = UUID("44444444-4444-4444-4444-444444444444")
CIKOS_EXECUTIVE_SUITES_ID = UUID("55555555-5555-5555-5555-555555555555")
CANDELARIA_HOSTEL_ID = UUID("66666666-6666-6666-6666-666666666666")
ANDINO_APARTHOTEL_ID = UUID("77777777-7777-7777-7777-777777777777")

# Demo hotel owner IDs — must match user IDs seeded in the users service.
DEMO_HOTEL_A_OWNER_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
DEMO_HOTEL_B_OWNER_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


PROPERTIES_DATA = [
    {
        "id": RENAISSANCE_ESTATE_ID,
        "id_owner": DEMO_HOTEL_A_OWNER_ID,
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
            "Bodega de Vinos",
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
        "id_owner": DEMO_HOTEL_A_OWNER_ID,
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
            "Terraza en Azotea",
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
            ("Juan Pérez", 5, date(2024, 8, 5), "Ubicación espectacular y servicio excepcional. El anfitrión se esforzó mucho para hacernos sentir bienvenidos. ¡Volveremos!"),
        ],
    },
    {
        "id": ALPINE_LODGE_ID,
        "id_owner": DEMO_HOTEL_B_OWNER_ID,
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
            "Biblioteca",
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
        "id_owner": DEMO_HOTEL_B_OWNER_ID,
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
            "Acceso Esnórquel",
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
    {
        "id": CIKOS_EXECUTIVE_SUITES_ID,
        "id_owner": DEMO_HOTEL_A_OWNER_ID,
        "name": "Hotel Cikos Executive Suites",
        "description": "Un hotel boutique urbano pensado para viajes de negocio y escapadas premium en Bogotá. La propiedad combina diseño contemporáneo, suites luminosas, espacios de coworking y una experiencia flexible para viajeros que llegan tarde, trabajan remoto o necesitan gestionar su reserva desde el panel del hotel. Sus habitaciones están equipadas con mobiliario ergonómico, domótica ligera, ropa de cama de alta gama y una terraza social con vistas a la ciudad.",
        "location": "Bogotá, Colombia",
        "latitude": 4.7110,
        "longitude": -74.0721,
        "price_per_night": 180000.0,
        "currency": "COP",
        "rating": 4.84,
        "review_count": 31,
        "bedrooms": 8,
        "bathrooms": 8.0,
        "max_guests": 24,
        "amenities": [
            "WiFi Empresarial de Alta Velocidad",
            "Desayuno Incluido",
            "Coworking Lounge",
            "Recepción 24 Horas",
            "Check-in Digital",
            "Terraza Panorámica",
            "Salas de Reunión",
            "Servicio de Traslado",
        ],
        "cancellation_policy": "Cancelación gratuita hasta 24 horas antes del check-in. Luego se cobra la primera noche.",
        "tax_rate": 0.19,
        "cleaning_fee": 25000.0,
        "images": [
            ("1", "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=800&q=80", "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=1920&q=90", "Fachada Hotel Cikos Executive Suites", 0, True),
            ("2", "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?w=800&q=80", "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?w=1920&q=90", "Suite Ejecutiva", 1, False),
            ("3", "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=800&q=80", "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=1920&q=90", "Lounge de trabajo", 2, False),
            ("4", "https://images.unsplash.com/photo-1551882547-ff40c63fe5fa?w=800&q=80", "https://images.unsplash.com/photo-1551882547-ff40c63fe5fa?w=1920&q=90", "Lobby y recepción", 3, False),
            ("5", "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?w=800&q=80", "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?w=1920&q=90", "Terraza panorámica", 4, False),
        ],
        "reviews": [
            ("Laura Sánchez", 5, date(2024, 9, 18), "Excelente opción en Bogotá para viaje de trabajo. Las suites son muy cómodas y el personal resolvió un cambio de reserva rapidísimo."),
            ("Andrés Melo", 5, date(2024, 8, 27), "Muy buena ubicación, internet estable y espacios comunes impecables. Ideal para combinar reuniones y descanso."),
        ],
    },
    {
        "id": CANDELARIA_HOSTEL_ID,
        "id_owner": DEMO_HOTEL_B_OWNER_ID,
        "name": "Hostal Boutique La Candelaria",
        "description": "Hostal boutique en pleno casco histórico de Bogotá, a pasos del Museo del Oro y la Plaza de Bolívar. Una casa colonial restaurada con patios interiores, café de autor y habitaciones acogedoras pensadas para mochileros y viajeros que buscan ambiente local. Cuenta con áreas comunes amplias, terraza con vista a los cerros y un equipo bilingüe que organiza tours guiados a precios económicos.",
        "location": "Bogotá, Colombia",
        "latitude": 4.5969,
        "longitude": -74.0728,
        "price_per_night": 95000.0,
        "currency": "COP",
        "rating": 4.55,
        "review_count": 18,
        "bedrooms": 4,
        "bathrooms": 4.0,
        "max_guests": 8,
        "amenities": [
            "WiFi Compartido",
            "Desayuno Casero",
            "Tours Guiados",
            "Cocina Compartida",
            "Terraza con Vista",
            "Recepción Bilingüe",
            "Lavandería",
            "Café de Autor",
        ],
        "cancellation_policy": "Cancelación gratuita hasta 48 horas antes del check-in. Sin reembolso después.",
        "tax_rate": 0.19,
        "cleaning_fee": 12000.0,
        "images": [
            ("1", "https://images.unsplash.com/photo-1555854877-bab0e564b8d5?w=800&q=80", "https://images.unsplash.com/photo-1555854877-bab0e564b8d5?w=1920&q=90", "Patio Colonial Hostal Candelaria", 0, True),
            ("2", "https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=800&q=80", "https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=1920&q=90", "Habitación Doble", 1, False),
            ("3", "https://images.unsplash.com/photo-1551776235-dde6c46def96?w=800&q=80", "https://images.unsplash.com/photo-1551776235-dde6c46def96?w=1920&q=90", "Cocina Compartida", 2, False),
            ("4", "https://images.unsplash.com/photo-1499678329028-101435549a4e?w=800&q=80", "https://images.unsplash.com/photo-1499678329028-101435549a4e?w=1920&q=90", "Terraza con vista a los cerros", 3, False),
            ("5", "https://images.unsplash.com/photo-1517840901100-8179e982acb7?w=800&q=80", "https://images.unsplash.com/photo-1517840901100-8179e982acb7?w=1920&q=90", "Sala común", 4, False),
        ],
        "reviews": [
            ("Camila Restrepo", 5, date(2024, 9, 25), "Ubicación inmejorable, atención cálida y desayuno delicioso. Ideal para conocer la Candelaria caminando."),
            ("Tomás Vargas", 4, date(2024, 7, 12), "Muy buena relación calidad-precio. Las habitaciones son básicas pero limpias y el ambiente es genial."),
        ],
    },
    {
        "id": ANDINO_APARTHOTEL_ID,
        "id_owner": DEMO_HOTEL_B_OWNER_ID,
        "name": "Aparthotel Andino Premium",
        "description": "Aparthotel ejecutivo en la zona financiera de Bogotá, a una cuadra del Centro Comercial Andino y rodeado de restaurantes premium. Las suites cuentan con cocina equipada, sala-comedor independiente y estaciones de trabajo ergonómicas, ideales para estancias largas o proyectos de consultoría. La propiedad incluye gimnasio 24 horas, sauna, salón ejecutivo y servicio de housekeeping diario.",
        "location": "Bogotá, Colombia",
        "latitude": 4.6680,
        "longitude": -74.0539,
        "price_per_night": 320000.0,
        "currency": "COP",
        "rating": 4.95,
        "review_count": 47,
        "bedrooms": 3,
        "bathrooms": 3.0,
        "max_guests": 6,
        "amenities": [
            "WiFi Empresarial",
            "Cocina Equipada",
            "Gimnasio 24 Horas",
            "Sauna y Spa",
            "Salón Ejecutivo",
            "Estación de Trabajo",
            "Housekeeping Diario",
            "Parqueadero Cubierto",
        ],
        "cancellation_policy": "Cancelación gratuita hasta 72 horas antes del check-in. Cancelación al 50% entre 24 y 72 horas.",
        "tax_rate": 0.19,
        "cleaning_fee": 45000.0,
        "images": [
            ("1", "https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?w=800&q=80", "https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?w=1920&q=90", "Fachada Aparthotel Andino", 0, True),
            ("2", "https://images.unsplash.com/photo-1631049307264-da0ec9d70304?w=800&q=80", "https://images.unsplash.com/photo-1631049307264-da0ec9d70304?w=1920&q=90", "Suite ejecutiva con cocina", 1, False),
            ("3", "https://images.unsplash.com/photo-1540541338287-41700207dee6?w=800&q=80", "https://images.unsplash.com/photo-1540541338287-41700207dee6?w=1920&q=90", "Estación de trabajo", 2, False),
            ("4", "https://images.unsplash.com/photo-1571902943202-507ec2618e8f?w=800&q=80", "https://images.unsplash.com/photo-1571902943202-507ec2618e8f?w=1920&q=90", "Gimnasio 24 horas", 3, False),
            ("5", "https://images.unsplash.com/photo-1545158535-c3f7168c28b6?w=800&q=80", "https://images.unsplash.com/photo-1545158535-c3f7168c28b6?w=1920&q=90", "Salón ejecutivo", 4, False),
        ],
        "reviews": [
            ("Daniela Ortiz", 5, date(2024, 10, 2), "La mejor opción para viaje de negocios largo en Bogotá. La suite parece un apartamento real y el gimnasio está impecable."),
            ("Felipe Hernández", 5, date(2024, 9, 5), "Servicio cinco estrellas, ubicación premium y muy silencioso a pesar de estar en plena Zona T."),
        ],
    },
]


# Map-search clusters: 8 properties per city, dispersed within ~3-5km of city center,
# so a Compose Maps viewport at zoom 12-13 surfaces 4-8 pins per area.
_MAP_CLUSTER_CITIES = (
    {
        "city": "Bogotá",
        "country": "Colombia",
        "uuid_prefix": "10000001",
        "center": (4.7110, -74.0721),
        "spread": (0.030, 0.040),
        "currency": "COP",
        "base_price": 280000.0,
        "cleaning_fee": 25000.0,
        "tax_rate": 0.19,
        "name_pool": (
            "Hotel Zona T Boutique",
            "Suites Chapinero Premium",
            "Casa Quinta Usaquén",
            "Apartahotel Salitre",
            "Hostal Macarena Arte",
            "Hotel Centro Internacional",
            "Loft Parque 93",
            "Hotel Modelia Confort",
        ),
    },
    {
        "city": "Medellín",
        "country": "Colombia",
        "uuid_prefix": "10000002",
        "center": (6.2476, -75.5658),
        "spread": (0.030, 0.040),
        "currency": "COP",
        "base_price": 240000.0,
        "cleaning_fee": 22000.0,
        "tax_rate": 0.19,
        "name_pool": (
            "Hotel El Poblado Lifestyle",
            "Suites Laureles Selva",
            "Casa Provenza Diseño",
            "Apartahotel Las Palmas",
            "Hostal Comuna 13 Color",
            "Hotel Centro Botero",
            "Loft Envigado Verde",
            "Hotel Sabaneta Familiar",
        ),
    },
    {
        "city": "Cartagena",
        "country": "Colombia",
        "uuid_prefix": "10000003",
        "center": (10.3997, -75.5144),
        "spread": (0.025, 0.035),
        "currency": "COP",
        "base_price": 420000.0,
        "cleaning_fee": 35000.0,
        "tax_rate": 0.19,
        "name_pool": (
            "Hotel Ciudad Amurallada",
            "Casa Getsemaní Boutique",
            "Suites Bocagrande Mar",
            "Apartamento Castillogrande",
            "Hostal San Diego Colonial",
            "Hotel Manga Tradicional",
            "Loft Crespo Aeropuerto",
            "Hotel Laguito Vista",
        ),
    },
    {
        "city": "Pasto",
        "country": "Colombia",
        "uuid_prefix": "10000004",
        "center": (1.2136, -77.2811),
        "spread": (0.020, 0.025),
        "currency": "COP",
        "base_price": 180000.0,
        "cleaning_fee": 18000.0,
        "tax_rate": 0.19,
        "name_pool": (
            "Hotel Galeras Centro",
            "Casa Colonial San Felipe",
        ),
    },
)


def _generate_map_cluster_entries() -> list[dict]:
    """
    Build a deterministic set of seed entries clustered in the major Colombian
    cities. Used to populate the mobile map-search feature with realistic pins.
    """
    entries: list[dict] = []
    owners = (DEMO_HOTEL_A_OWNER_ID, DEMO_HOTEL_B_OWNER_ID)
    # Rotated through deterministically by (city_idx, n). Each tuple is an
    # Unsplash photo id; the seed builds the 800w (cover) and 1920w (hires)
    # URLs from it. Mix of hotel exteriors, lobbies, suites and pools so the
    # map cards don't all look like the same property.
    image_ids = (
        "1551882547-ff40c63fe5fa",  # contemporary hotel facade
        "1566073771259-6a8506099945",  # boutique hotel exterior
        "1582719478250-c89cae4dc85b",  # urban hotel building
        "1564013799919-ab600027ffc6",  # luxury suite
        "1505693416388-ac5ce068fe85",  # modern bedroom
        "1522708323590-d24dbb6b0267",  # design bedroom
        "1559827260-dc66d52bef19",  # beachfront / outdoor
        "1571508601155-8a95d1df991c",  # cozy living room
        "1542314831-068cd1dbfeeb",  # rooftop terrace
        "1455587734955-081b22074882",  # pool
        "1551776235-dde6c46def96",  # apartment kitchen
        "1540541338287-41700207dee6",  # workstation / executive
    )
    img_count = len(image_ids)

    for city_idx, spec in enumerate(_MAP_CLUSTER_CITIES):
        center_lat, center_lng = spec["center"]
        lat_spread, lng_spread = spec["spread"]
        for n, name in enumerate(spec["name_pool"]):
            seq = n + 1
            uid_hex = f"{spec['uuid_prefix']}-0000-0000-0000-{seq:012d}"
            # Deterministic angular spread around center: 8 points around a circle,
            # alternating two radii so they don't sit on a single ring.
            angle = (2 * math.pi * n) / len(spec["name_pool"])
            radius_factor = 0.6 if n % 2 == 0 else 1.0
            latitude = round(center_lat + radius_factor * lat_spread * math.cos(angle), 6)
            longitude = round(center_lng + radius_factor * lng_spread * math.sin(angle), 6)
            owner = owners[(city_idx + n) % len(owners)]
            entries.append(
                {
                    "id": UUID(uid_hex),
                    "id_owner": owner,
                    "name": name,
                    "description": (
                        f"{name} en {spec['city']}. Propiedad de prueba para "
                        "la búsqueda avanzada en mapa: incluye pin con coordenadas "
                        "geográficas reales y datos completos."
                    ),
                    "location": f"{spec['city']}, {spec['country']}",
                    "latitude": latitude,
                    "longitude": longitude,
                    "price_per_night": spec["base_price"] + n * 35000.0,
                    "currency": spec["currency"],
                    "rating": round(4.2 + (n % 5) * 0.15, 2),
                    "review_count": 12 + n,
                    "bedrooms": 1 + (n % 3),
                    "bathrooms": float(1 + (n % 2)),
                    "max_guests": 2 + (n % 4),
                    "amenities": [
                        "WiFi de Alta Velocidad",
                        "Recepción 24 Horas",
                        "Aire Acondicionado",
                        "Desayuno Incluido",
                    ],
                    "cancellation_policy": (
                        "Cancelación gratuita hasta 24 horas antes del check-in."
                    ),
                    "tax_rate": spec["tax_rate"],
                    "cleaning_fee": spec["cleaning_fee"],
                    "images": [
                        (
                            str(slot + 1),
                            f"https://images.unsplash.com/photo-{photo_id}?w=800&q=80",
                            f"https://images.unsplash.com/photo-{photo_id}?w=1920&q=90",
                            alt_text,
                            slot,
                            slot == 0,
                        )
                        for slot, (photo_id, alt_text) in enumerate(
                            (
                                (
                                    image_ids[(city_idx * 3 + n) % img_count],
                                    f"Vista principal {name}",
                                ),
                                (
                                    image_ids[(city_idx * 3 + n + 4) % img_count],
                                    f"Habitación {name}",
                                ),
                                (
                                    image_ids[(city_idx * 3 + n + 8) % img_count],
                                    f"Áreas comunes {name}",
                                ),
                            )
                        )
                    ],
                    "reviews": [
                        (
                            "Cliente Verificado",
                            5,
                            date(2024, 9, 1),
                            f"Estancia agradable en {spec['city']}, ubicación práctica para moverse en la ciudad.",
                        ),
                    ],
                }
            )
    return entries


if settings.seed_map_clusters:
    PROPERTIES_DATA.extend(_generate_map_cluster_entries())


def sync_demo_properties_seed(session: Session) -> None:
    """Create or update demo properties and backfill any missing demo assets."""
    try:
        for prop_data in PROPERTIES_DATA:
            existing = session.get(Property, prop_data["id"])
            amenities = json.dumps(prop_data["amenities"])
            if existing is None:
                existing = Property(id=prop_data["id"])
                session.add(existing)

            existing.id_owner = prop_data.get("id_owner")
            existing.name = prop_data["name"]
            existing.description = prop_data["description"]
            existing.location = prop_data["location"]
            existing.latitude = prop_data["latitude"]
            existing.longitude = prop_data["longitude"]
            existing.price_per_night = prop_data["price_per_night"]
            existing.currency = prop_data["currency"]
            existing.rating = prop_data["rating"]
            existing.review_count = prop_data["review_count"]
            existing.bedrooms = prop_data["bedrooms"]
            existing.bathrooms = prop_data["bathrooms"]
            existing.max_guests = prop_data["max_guests"]
            existing.amenities = amenities
            existing.cancellation_policy = prop_data["cancellation_policy"]
            existing.tax_rate = prop_data["tax_rate"]
            existing.cleaning_fee = prop_data["cleaning_fee"]
            existing.status = 1

        session.commit()
        sync_property_policies_seed(session)

        for prop_data in PROPERTIES_DATA:
            existing_images = session.exec(
                select(PropertyImage).where(PropertyImage.property_id == prop_data["id"])
            ).all()
            existing_by_position = {
                image.position: image for image in existing_images if image.position is not None
            }
            existing_by_url = {
                image.url: image for image in existing_images if image.url is not None
            }
            for _, url, url_hires, alt_text, position, is_cover in prop_data["images"]:
                existing_image = existing_by_position.get(position) or existing_by_url.get(url)
                if existing_image is None:
                    existing_image = PropertyImage(
                        property_id=prop_data["id"],
                        url=url,
                        url_hires=url_hires,
                        alt_text=alt_text,
                        position=position,
                        is_cover=is_cover,
                    )
                    session.add(existing_image)
                else:
                    existing_image.url = url
                    existing_image.url_hires = url_hires
                    existing_image.alt_text = alt_text
                    existing_image.position = position
                    existing_image.is_cover = is_cover

                existing_by_position[position] = existing_image
                existing_by_url[url] = existing_image

        session.commit()

        for prop_data in PROPERTIES_DATA:
            existing_reviews = session.exec(
                select(PropertyReview).where(PropertyReview.property_id == prop_data["id"])
            ).all()
            existing_reviews_by_date = {
                review.review_date: review for review in existing_reviews
            }
            for author, rating, review_date, comment in prop_data["reviews"]:
                existing_review = existing_reviews_by_date.get(review_date)
                if existing_review is None:
                    existing_review = PropertyReview(
                        property_id=prop_data["id"],
                        author=author,
                        rating=rating,
                        review_date=review_date,
                        comment=comment,
                        verified_stay=True,
                    )
                    session.add(existing_review)
                else:
                    existing_review.author = author
                    existing_review.rating = rating
                    existing_review.comment = comment
                    existing_review.verified_stay = True

                existing_reviews_by_date[review_date] = existing_review

        session.commit()
    except Exception:
        session.rollback()
        raise


def seed_properties_if_empty(session: Session) -> None:
    """Backward-compatible alias for syncing demo properties and assets."""
    sync_demo_properties_seed(session)


def sync_property_policies_seed(session: Session) -> None:
    """Create or update demo cancellation policies for seeded properties."""
    policies = [
        {
            "property_id": RENAISSANCE_ESTATE_ID,
            "policy_type": "full_refund",
            "minimum_notice_hours": 48,
            "penalty_percentage": 0,
            "timezone": "Europe/Rome",
        },
        {
            "property_id": BEACHFRONT_PENTHOUSE_ID,
            "policy_type": "partial_refund",
            "minimum_notice_hours": 24,
            "penalty_percentage": 25,
            "timezone": "America/New_York",
        },
        {
            "property_id": ALPINE_LODGE_ID,
            "policy_type": "non_refundable",
            "minimum_notice_hours": 72,
            "penalty_percentage": 100,
            "timezone": "Europe/Paris",
        },
        {
            "property_id": TROPICAL_VILLA_ID,
            "policy_type": "full_refund",
            "minimum_notice_hours": 24,
            "penalty_percentage": 0,
            "timezone": "Pacific/Tahiti",
        },
        {
            "property_id": CIKOS_EXECUTIVE_SUITES_ID,
            "policy_type": "full_refund",
            "minimum_notice_hours": 24,
            "penalty_percentage": 0,
            "timezone": "America/Bogota",
        },
        {
            "property_id": CANDELARIA_HOSTEL_ID,
            "policy_type": "full_refund",
            "minimum_notice_hours": 48,
            "penalty_percentage": 0,
            "timezone": "America/Bogota",
        },
        {
            "property_id": ANDINO_APARTHOTEL_ID,
            "policy_type": "partial_refund",
            "minimum_notice_hours": 72,
            "penalty_percentage": 50,
            "timezone": "America/Bogota",
        },
    ]

    for policy_data in policies:
        existing = session.exec(
            select(PropertyCancellationPolicy).where(
                PropertyCancellationPolicy.property_id == policy_data["property_id"]
            )
        ).first()
        if existing is None:
            existing = PropertyCancellationPolicy(property_id=policy_data["property_id"])
            session.add(existing)

        existing.policy_type = policy_data["policy_type"]
        existing.minimum_notice_hours = policy_data["minimum_notice_hours"]
        existing.penalty_percentage = policy_data["penalty_percentage"]
        existing.timezone = policy_data["timezone"]
        existing.is_active = True

    explicit_property_ids = {p["property_id"] for p in policies}
    all_property_ids = session.exec(select(Property.id)).all()
    for property_id in all_property_ids:
        if property_id in explicit_property_ids:
            continue
        existing = session.exec(
            select(PropertyCancellationPolicy).where(
                PropertyCancellationPolicy.property_id == property_id
            )
        ).first()
        if existing is not None:
            continue
        session.add(
            PropertyCancellationPolicy(
                property_id=property_id,
                policy_type="full_refund",
                minimum_notice_hours=48,
                penalty_percentage=0,
                timezone="America/Bogota",
                is_active=True,
            )
        )

    session.commit()


def seed_property_policies_if_missing(session: Session) -> None:
    """Backward-compatible alias for syncing demo cancellation policies."""
    sync_property_policies_seed(session)
