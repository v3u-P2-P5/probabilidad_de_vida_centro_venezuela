"""Consejos de seguridad post-terremoto (contenido curado, verbatim).

Fuente única de verdad: la usa tanto la página de Consejos (pages/5) como la
skill get_safety_tips del asistente, para no duplicar la prosa. NO reescribir.
"""

# 7 secciones por idioma: (título, [tips...]). El orden es estable (ver TEMA_INDICE).
SAFETY_TIPS = {
    "es": [
        ("⚠️ Durante una réplica", [
            "**Agáchate, Cúbrete y Agárrate**: bajo una mesa firme, protege cabeza y cuello.",
            "Aléjate de ventanas, vidrios, fachadas, balcones y objetos que puedan caer.",
            "Si estás en cama, quédate y cúbrete la cabeza con una almohada.",
            "Si estás en silla de ruedas, frena, e inclínate cubriendo cabeza y cuello.",
            "No uses ascensores. No corras hacia las escaleras durante el temblor.",
            "Si estás al aire libre, ve a un espacio abierto lejos de edificios, postes y cables.",
            "Si conduces, detente en un lugar seguro y permanece dentro del vehículo.",
        ]),
        ("🏚️ Edificios y estructuras", [
            "**No entres** a edificaciones con grietas grandes, columnas dañadas, pisos hundidos o inclinación: pueden colapsar en una réplica.",
            "Si tu casa quedó dañada, sal con calma y no regreses hasta que un técnico la evalúe.",
            "Cuidado con escombros, vidrios y estructuras inestables al caminar.",
            "Reporta edificios en riesgo a Protección Civil.",
        ]),
        ("🔥 Gas, electricidad y agua", [
            "**Si hueles gas**: no enciendas luces, fósforos ni aparatos; cierra la llave, abre ventanas y sal.",
            "Corta la electricidad si ves cables dañados, chispas u olor a quemado.",
            "Cierra el agua si hay fugas. No bebas agua de la red hasta que se confirme potable.",
            "No uses velas; usa linternas para evitar incendios.",
        ]),
        ("🩹 Salud y primeros auxilios", [
            "Atiende primero a quien tenga hemorragias graves o dificultad para respirar.",
            "No muevas a personas con posibles lesiones de columna salvo peligro inmediato.",
            "Mantén a mano medicinas esenciales y botiquín.",
            "Si hay tiempo: lávate las manos y sécalas bien antes de ayudar a personas que lo necesiten.",
        ]),
        ("🎒 Kit de emergencia", [
            "Agua (4 L por persona/día), alimentos no perecederos y abrelatas.",
            "Linterna, radio a pilas, baterías y carga portátil para el teléfono.",
            "Botiquín, medicinas, copia de documentos, algo de efectivo y silbato.",
            "Ropa, abrigo, calzado resistente y artículos de higiene.",
        ]),
        ("👪 Familia y reunificación", [
            "Acuerda un **punto de encuentro** y un **contacto fuera de la zona**.",
            "Para buscar o registrar a un familiar: [Desaparecidos Terremoto Venezuela](https://desaparecidosterremotovenezuela.com/) · [Cruz Roja Venezolana](https://cruzroja.ve/).",
            "Ten a mano una lista de contactos en papel por si el teléfono falla.",
            "Enseña a los niños a quién llamar y a dónde ir.",
        ]),
        ("📰 Información y precauciones", [
            "Sigue solo fuentes oficiales (Protección Civil, USGS, OCHA). Evita rumores.",
            "Mantén el teléfono con batería.",
            "Espera réplicas durante días o semanas: mantén la precaución.",
        ]),
    ],
    "en": [
        ("⚠️ During an aftershock", [
            "**Drop, Cover, Hold On**: under a sturdy table; protect head and neck.",
            "Stay away from windows, glass, facades, balconies and falling objects.",
            "If in bed, stay and cover your head with a pillow.",
            "In a wheelchair, lock it and lean over protecting head and neck.",
            "Do not use elevators. Do not run to stairs during shaking.",
            "Outdoors, move to an open area away from buildings, poles and wires.",
            "If driving, stop somewhere safe and stay inside the vehicle.",
        ]),
        ("🏚️ Buildings and structures", [
            "**Do not enter** buildings with large cracks, damaged columns, sunken floors or leaning: they may collapse in an aftershock.",
            "If your home is damaged, leave calmly and don't return until inspected.",
            "Watch for debris, glass and unstable structures.",
            "Report at-risk buildings to Civil Protection; do not improvise rescues in collapsed structures.",
        ]),
        ("🔥 Gas, power and water", [
            "**If you smell gas**: no lights, matches or appliances; shut the valve, open windows, leave.",
            "Cut power if you see damaged wiring, sparks or burning smell.",
            "Shut water if leaking. Do not drink tap water until confirmed safe.",
            "Avoid candles; use flashlights to prevent fires.",
        ]),
        ("🩹 Health and first aid", [
            "Help first those with severe bleeding or breathing difficulty.",
            "Do not move people with possible spinal injuries unless in immediate danger.",
            "Keep essential medicines and a first-aid kit at hand.",
            "Wash hands; contaminated water and crowding increase disease.",
        ]),
        ("🎒 Emergency kit", [
            "Water (4 L per person/day), non-perishable food and a can opener.",
            "Flashlight, battery radio, batteries and a power bank.",
            "First-aid kit, medicines, copies of documents, some cash and a whistle.",
            "Clothing, warm layers, sturdy shoes and hygiene items.",
        ]),
        ("👪 Family and reunification", [
            "Agree a **meeting point** and an **out-of-area contact**.",
            "To search or register a relative: [Desaparecidos Terremoto Venezuela](https://desaparecidosterremotovenezuela.com/) · [Venezuelan Red Cross](https://cruzroja.ve/).",
            "Keep a paper contact list in case phones fail.",
            "Teach children whom to call and where to go.",
        ]),
        ("📰 Information and precautions", [
            "Follow only official sources (Civil Protection, USGS, OCHA). Avoid rumors.",
            "Keep your phone charged.",
            "Expect aftershocks for days or weeks: stay cautious.",
        ]),
    ],
}

# Tema estable -> índice de sección (para la skill get_safety_tips).
TEMA_INDICE = {
    "replica": 0, "edificios": 1, "gas_luz_agua": 2, "primeros_auxilios": 3,
    "kit_emergencia": 4, "reunificacion": 5, "informacion": 6,
}
TEMA_INVERSO = {v: k for k, v in TEMA_INDICE.items()}

TELEFONOS_EMERGENCIA = ["171", "911"]
