"""
seed_data.py — Datos estáticos para generación sintética realista.

Contiene listas de nombres, productos, empresas y datos propios del sector
de climatización JDDC. Importado exclusivamente por synthetic_seeder.py.

DEVIA: backend/modules/db_simulator/DEVIA.md
"""

# ─── Familias de producto ─────────────────────────────────────────────────────

FAMILIAS = [
    (1,  "Splits Pared",          "Unidades split pared residencial e industrial"),
    (2,  "Multi-Split",           "Sistemas multi-split 2 a 5 unidades interiores"),
    (3,  "Cassettes",             "Unidades cassette para techo 2x2 y 4x4 vías"),
    (4,  "Conductos",             "Unidades de conductos ocultos"),
    (5,  "Suelo y Techo",         "Unidades suelo-techo para locales y oficinas"),
    (6,  "VRV y VRF",             "Sistemas de volumen de refrigerante variable"),
    (7,  "Chillers y Enfriadoras","Enfriadoras de agua y bombas de calor inverter"),
    (8,  "Bombas de Calor AA",    "Aerotermia y bombas de calor aire-agua"),
    (9,  "Gas Refrigerante",      "R-32, R-410A, R-407C y otros refrigerantes"),
    (10, "Tubería y Accesorios",  "Cobre, aislante, soportes y valvulería"),
    (11, "Material Eléctrico",    "Cable, cuadros, protecciones y termostatos"),
    (12, "Soportes y Anclajes",   "Bancadas, soportes antisismicos y antivibratorios"),
    (13, "Filtros y Repuestos",   "Filtros HEPA, filtros de carbón y recambios"),
    (14, "Herramientas",          "Manómetros, bombas vacío y herramientas específicas"),
    (15, "Servicios",             "Mano de obra instalación, mantenimiento y SAT"),
]

# ─── Almacenes ────────────────────────────────────────────────────────────────

ALMACENES = [
    (1, "Almacén Principal",   "Nave principal JDDC, Pol. Industrial"),
    (2, "Almacén Obra",        "Stock en obra asignado a técnicos"),
    (3, "Almacén Repuestos",   "Recambios y repuestos urgentes"),
    (4, "Almacén Consignación","Equipos en consignación de proveedor"),
]

# ─── Proveedores ──────────────────────────────────────────────────────────────

PROVEEDORES = [
    (1,  "Daikin España S.A.U.",           "B82345678", "91 123 45 67"),
    (2,  "Mitsubishi Electric Europe B.V.","B91234567", "91 234 56 78"),
    (3,  "Fujitsu General España S.L.",    "B87654321", "93 345 67 89"),
    (4,  "Samsung Electronics Iberia S.A.","A12345678", "91 456 78 90"),
    (5,  "LG Electronics España S.L.",     "B23456789", "91 567 89 01"),
    (6,  "Panasonic España S.A.",          "A34567890", "91 678 90 12"),
    (7,  "Toshiba Air Conditioning",       "B45678901", "93 789 01 23"),
    (8,  "Carrier España S.L.",            "B56789012", "91 890 12 34"),
    (9,  "Climaequip Distribución S.L.",   "B67890123", "96 901 23 45"),
    (10, "Frigicoll S.A.",                 "A78901234", "93 012 34 56"),
    (11, "Ciatesa S.A.",                   "A89012345", "91 123 45 67"),
    (12, "Chemours Fluoroproducts",        "A90123456", "91 234 56 78"),
    (13, "Climalife Ibérica S.L.",         "B01234567", "93 345 67 89"),
    (14, "Rotex Heating Systems S.L.",     "B12345670", "91 456 78 90"),
    (15, "Emmeti España S.L.",             "B23456780", "96 567 89 01"),
]

# ─── Empleados / Recursos ─────────────────────────────────────────────────────

RECURSOS = [
    # (codigo, descripcion, codpadre, orden, nif, telefono)
    (1,  "JDDC CLIMATIZACIÓN S.L.",   0,  1,  "B12345678",  "96 100 00 00"),
    (2,  "Departamento Técnico",       1,  2,  "",           ""),
    (3,  "Departamento Comercial",     1,  3,  "",           ""),
    (4,  "Administración",             1,  4,  "",           ""),
    (5,  "GARCÍA GIL, ADRIÁN",         2,  5,  "48510320P",  "601 107 251"),
    (6,  "MARTÍNEZ López, FRANCISCO",  2,  6,  "52345678Q",  "612 345 678"),
    (7,  "SÁNCHEZ RUIZ, MIGUEL",       2,  7,  "63456789R",  "623 456 789"),
    (8,  "FERNÁNDEZ MORA, CARLOS",     2,  8,  "74567890S",  "634 567 890"),
    (9,  "RODRÍGUEZ VEGA, ANA",        3,  9,  "85678901T",  "645 678 901"),
    (10, "PÉREZ JIMÉNEZ, LAURA",       3, 10,  "96789012U",  "656 789 012"),
    (11, "GÓMEZ SERRANO, JUAN",        3, 11,  "07890123V",  "667 890 123"),
    (12, "DÍAZ MOLINA, CARMEN",        4, 12,  "18901234W",  "678 901 234"),
]

# ─── Artículos: equipos de climatización ─────────────────────────────────────

ARTICULOS_DATA = [
    # (ref, nombre, descripcioncorta, precio_venta, codfamilia, codproveedor, stock)
    # -- Splits Pared (familia 1) --
    ("DAI-FTXC25C", "Daikin FTXC25C Split Pared 2.500W R-32",         "Split 2.5kW Daikin",   699.00,  1, 1, 8.0),
    ("DAI-FTXC35C", "Daikin FTXC35C Split Pared 3.500W R-32",         "Split 3.5kW Daikin",   849.00,  1, 1, 12.0),
    ("DAI-FTXC50C", "Daikin FTXC50C Split Pared 5.000W R-32",         "Split 5kW Daikin",    1090.00,  1, 1, 6.0),
    ("DAI-FTXM35R", "Daikin FTXM35R Emura III 3.500W R-32 Blanco",    "Emura 3.5kW Daikin",  1290.00,  1, 1, 4.0),
    ("MIT-MSZ-AP25VGK","Mitsubishi MSZ-AP25VGK 2.500W R-32",          "Split 2.5kW Mitsu",    749.00,  1, 2, 7.0),
    ("MIT-MSZ-AP35VGK","Mitsubishi MSZ-AP35VGK 3.500W R-32",          "Split 3.5kW Mitsu",    920.00,  1, 2, 10.0),
    ("MIT-MSZ-AP50VGK","Mitsubishi MSZ-AP50VGK 5.000W R-32",          "Split 5kW Mitsu",     1180.00,  1, 2, 5.0),
    ("FUJ-ASY25MUCG",  "Fujitsu ASY25MUCG 2.500W R-32",               "Split 2.5kW Fujitsu",  680.00,  1, 3, 9.0),
    ("FUJ-ASY35MUCG",  "Fujitsu ASY35MUCG 3.500W R-32",               "Split 3.5kW Fujitsu",  820.00,  1, 3, 11.0),
    ("SAM-AR12TXH",    "Samsung AR12TXHQASINEU WindFree 3.500W R-32",  "Split 3.5kW Samsung",  780.00,  1, 4, 6.0),
    ("LGS12ET",        "LG S12ET NSJ Split 3.500W R-32 Dual Inverter", "Split 3.5kW LG",       720.00,  1, 5, 8.0),
    ("PAN-CS-TZ25WKE", "Panasonic CS-TZ25WKE 2.500W R-32",            "Split 2.5kW Panasonic",710.00,  1, 6, 5.0),
    ("PAN-CS-TZ35WKE", "Panasonic CS-TZ35WKE 3.500W R-32",            "Split 3.5kW Panasonic",860.00,  1, 6, 7.0),
    # -- Multi-Split (familia 2) --
    ("DAI-3MXM52N",    "Daikin 3MXM52N Unidad Exterior 3x1 5.200W",   "Multi 3x1 Daikin",    1450.00,  2, 1, 3.0),
    ("DAI-4MXM80N",    "Daikin 4MXM80N Unidad Exterior 4x1 8.000W",   "Multi 4x1 Daikin",    2150.00,  2, 1, 2.0),
    ("MIT-MXZ-3F54VF3","Mitsubishi MXZ-3F54VF3 Exterior 3x1 5.400W", "Multi 3x1 Mitsu",     1550.00,  2, 2, 3.0),
    # -- Cassettes (familia 3) --
    ("DAI-FCAG35A",    "Daikin FCAG35A Cassette 4 vías 3.500W R-32",  "Cassette 3.5kW Daikin",950.00, 3, 1, 4.0),
    ("MIT-PLA-M35EA",  "Mitsubishi PLA-M35EA Cassette 3.500W R-32",   "Cassette 3.5kW Mitsu", 980.00, 3, 2, 3.0),
    ("MIT-PLA-M71EA",  "Mitsubishi PLA-M71EA Cassette 7.100W R-410A", "Cassette 7.1kW Mitsu",1450.00, 3, 2, 2.0),
    # -- Conductos (familia 4) --
    ("DAI-FBQ35D",     "Daikin FBQ35D Conductos Ocult. 3.500W R-410A","Conductos 3.5kW Daikin",1100.00,4, 1, 3.0),
    ("MIT-SEZ-M35DA",  "Mitsubishi SEZ-M35DA Conductos 3.500W R-32",  "Conductos 3.5kW Mitsu",1150.00,4, 2, 2.0),
    # -- VRV/VRF (familia 6) --
    ("DAI-RXYSQ4T7V1", "Daikin RXYSQ4T7V1 VRV IV 11.2kW R-410A",     "VRV 11.2kW Daikin",  4800.00,  6, 1, 1.0),
    ("MIT-PUMY-P125YKM","Mitsubishi City Multi 14kW R-410A",           "City Multi 14kW",    5200.00,  6, 2, 1.0),
    # -- Gas Refrigerante (familia 9) --
    ("GAS-R32-10KG",   "Gas Refrigerante R-32 Botella 10kg",           "R-32 10kg",           180.00,  9, 12, 20.0),
    ("GAS-R410A-10KG", "Gas Refrigerante R-410A Botella 10kg",         "R-410A 10kg",         220.00,  9, 12, 15.0),
    ("GAS-R407C-10KG", "Gas Refrigerante R-407C Botella 10kg",         "R-407C 10kg",         195.00,  9, 13, 10.0),
    ("GAS-R32-5KG",    "Gas Refrigerante R-32 Botella 5kg",            "R-32 5kg",             95.00,  9, 12, 25.0),
    # -- Tuberías y accesorios (familia 10) --
    ("TUB-1/4-3/8-3M", "Tubo Cobre 1/4\" x 3/8\" Aislado 3m",         "Tubo cobre 3m",        42.00, 10, 9,  30.0),
    ("TUB-1/4-1/2-3M", "Tubo Cobre 1/4\" x 1/2\" Aislado 3m",         "Tubo cobre 3m",        48.00, 10, 9,  25.0),
    ("TUB-1/4-5/8-3M", "Tubo Cobre 1/4\" x 5/8\" Aislado 3m",         "Tubo cobre 3m",        55.00, 10, 9,  20.0),
    ("VAL-3V-1/2",     "Válvula de Servicio 3 Vías 1/2\"",             "Válvula 3v 1/2",       28.00, 10, 9,  40.0),
    ("AISL-TUBO-9MM",  "Aislante Armaflex Tubo 9mm x 2m",              "Aislante 9mm",          8.50, 10, 9,  100.0),
    ("AISL-TUBO-13MM", "Aislante Armaflex Tubo 13mm x 2m",             "Aislante 13mm",        10.50, 10, 9,  80.0),
    ("SOPORTE-SPLIT",  "Soporte Mural Aluminio para Unidad Ext.",       "Soporte ext.",         35.00, 12, 9,  50.0),
    # -- Material Eléctrico (familia 11) --
    ("TERM-WIFI-4",    "Termostato WiFi Digital 4 hilos 230V",         "Termostato WiFi",      85.00, 11, 9,  20.0),
    ("TERM-PROG-2",    "Termostato Programable 2 hilos",               "Termostato prog.",     45.00, 11, 9,  30.0),
    ("CAB-3G-1.5-100M","Cable Manguera 3G x 1.5mm² 100m",             "Cable 3G 1.5 100m",   125.00, 11, 9,  8.0),
    ("INTEMP-10A",     "Interruptor Magnetotérmico 10A",               "Magnetot. 10A",        18.00, 11, 9,  50.0),
    # -- Filtros y Repuestos (familia 13) --
    ("FILT-DAI-KAF970","Filtro Aire Daikin KAF970A46",                "Filtro Daikin",        22.00, 13, 1,  15.0),
    ("FILT-MIT-MAC576","Filtro Aire Mitsubishi MAC-576FT-E",           "Filtro Mitsu",         19.50, 13, 2,  20.0),
    ("COND-DAIKIN-6L", "Condensado Daikin Bandeja 6L",                "Condensado 6L",        55.00, 13, 1,  10.0),
    # -- Servicios (familia 15) --
    ("MO-INSTAL-SPLIT","Mano de Obra Instalación Split",               "MO instalación",      180.00, 15, 0,   0.0),
    ("MO-MANT-ANUAL",  "Mantenimiento Preventivo Anual Split",         "Mantenimiento anual", 120.00, 15, 0,   0.0),
    ("MO-SAT-HORA",    "Servicio Asistencia Técnica — Hora",           "SAT hora",             75.00, 15, 0,   0.0),
    ("MO-RECAR-GAS",   "Recarga Gas Refrigerante — Intervención",      "Recarga gas",          95.00, 15, 0,   0.0),
    ("MO-DESPLAZAM",   "Desplazamiento Técnico",                       "Desplazamiento",       45.00, 15, 0,   0.0),
]

# ─── Clientes ─────────────────────────────────────────────────────────────────

CLIENTES_DATA = [
    # (nombre, cif, poblacion, codpostal, provincia, telefono, email, codagente)
    ("CONSTRUCCIONES MARTÍNEZ E HIJOS S.L.",  "B12011001","Valencia",   "46001","Valencia",   "963 100 101","contratas@martinez.es",   9),
    ("PROMOTORA LEVANTE S.A.",                "A12011002","Valencia",   "46010","Valencia",   "963 200 202","info@promlevante.com",     9),
    ("COMUNIDAD DE PROPIETARIOS C/ MAYOR 14", "H12011003","Torrent",    "46900","Valencia",   "963 300 303","admin@copropietarios.es",  10),
    ("HOSTELERÍA DÍAZ S.L.",                  "B12011004","Gandía",     "46700","Valencia",   "962 100 104","hosteleria@diaz.com",      9),
    ("CLÍNICA DENTAL SÁNCHEZ Y ASOCIADOS",    "B12011005","Sagunto",    "46500","Valencia",   "962 200 205","clinica@sanchez.es",       10),
    ("MERCADONA S.A.",                        "A46103834","Alboraya",   "46120","Valencia",   "961 300 306","proveedores@mercadona.com",9),
    ("HOTEL MARINA RESORT S.L.",              "B12011007","Cullera",    "46400","Valencia",   "961 400 407","mant@marinaresort.com",    9),
    ("TALLERES MECÁNICOS PÉREZ S.L.",         "B12011008","Alzira",     "46600","Valencia",   "962 500 508","taller@perez.es",         10),
    ("RESIDENCIA TERCERA EDAD SOL Y MAR S.A.","A12011009","Xàtiva",    "46800","Valencia",   "962 600 609","residencia@solymar.com",  9),
    ("COLEGIO SALESIANO SAN JOSÉ",            "G12011010","Bétera",     "46117","Valencia",   "963 700 710","admin@salesianos.es",     10),
    ("CENTRO COMERCIAL AQUA S.A.",            "A12011011","Valencia",   "46011","Valencia",   "963 800 811","tecnico@ccaqua.com",       9),
    ("URBANIZACIÓN LOS NARANJOS FASE II",     "H12011012","Paterna",    "46980","Valencia",   "963 900 912","admfinca@losnaranjos.es", 10),
    ("GARCIA FERNÁNDEZ, ANTONIO",             "52300001P","Manises",    "46940","Valencia",   "609 100 001","agf@gmail.com",            9),
    ("LÓPEZ HERNÁNDEZ, MANUEL",               "63410002Q","Mislata",    "46920","Valencia",   "618 200 002","mlh@hotmail.com",          9),
    ("RODRÍGUEZ MARTÍN, TERESA",              "74520003R","Burjassot",  "46100","Valencia",   "627 300 003","trodriguez@gmail.com",     10),
    ("OFICINAS CENTRALES BANCAJA REAL S.A.",  "A46200014","Valencia",   "46002","Valencia",   "963 001 400","infraestructuras@bancajareal.es",9),
    ("NAVE INDUSTRIAL POLÍGONO FUENTE DEL JARRO","B12011015","Paterna","46988","Valencia",   "961 150 150","naves@fuentejarro.com",    9),
    ("SUPERMERCADOS CONSUM S.COOP.",          "F46218167","Sedaví",     "46910","Valencia",   "963 250 250","mant@consum.es",           9),
    ("FABRICA MUEBLES MODERNOS S.L.",         "B12011018","Yecla",      "30510","Murcia",     "968 180 180","fmm@muebles.es",           10),
    ("AUTOMOCIÓN LEVANTINA S.A.",             "A12011019","Almussafes", "46440","Valencia",   "961 190 190","mantenimiento@autolevantina.com",9),
    ("COMUNIDAD PROPIETARIOS AVENIDA BLASCO IBÁÑEZ 22","H12011020","Valencia","46010","Valencia","963 200 200","comunidad@blasco22.com",10),
    ("GYM POWER FITNESS S.L.",                "B12011021","Ontinyent",  "46870","Valencia",   "962 210 210","gym@powerfitness.es",     9),
    ("CASA RURAL LA ALQUERIA",                "B12011022","Llutxent",   "46838","Valencia",   "962 220 220","casarural@alqueria.com",  10),
    ("ACADEMIA DE IDIOMAS GLOBAL LINGUA",     "B12011023","Aldaia",     "46960","Valencia",   "963 230 230","academia@globalingua.es", 9),
    ("MORALES RUIZ, CARLOS",                  "85630024S","L'Eliana",   "46183","Valencia",   "636 240 024","cmr@gmail.com",           9),
    ("IMPRENTA GRÁFICAS DEL TURIA S.L.",      "B12011025","Quart de Poblet","46930","Valencia","963 250 025","imprenta@graficasdelturia.com",10),
    ("BAR RESTAURANTE EL PATIO",              "B12011026","Sueca",      "46410","Valencia",   "961 260 026","elpatio@hosteleria.com",  9),
    ("PISCINAS Y JARDINES MEDITERRÁNEO S.L.", "B12011027","Torrent",    "46900","Valencia",   "963 270 027","piscinas@mediterran.com", 10),
    ("ELECTRIFICACIONES NORTE S.L.",          "B12011028","Llíria",     "46160","Valencia",   "963 280 028","electro@norte.es",        9),
    ("PÉREZ NAVARRO, ISABEL",                 "96740029T","Picanya",    "46210","Valencia",   "645 290 029","ipn@hotmail.com",         10),
    ("ASTILLEROS Y MANTENIMIENTO MARINA S.A.","A12011030","Gandia",     "46780","Valencia",   "962 300 030","astilleros@marinagandia.com",9),
    ("CLÍNICA VETERINARIA MASCOTVET",         "B12011031","Moncada",    "46113","Valencia",   "963 310 031","vet@mascotvet.com",       9),
    ("INDUSTRIAS METALÚRGICAS VIDAL S.L.",    "B12011032","Quart de Poblet","46930","Valencia","963 320 032","imv@metalvidal.com",      10),
    ("COMUNIDAD SANTA ROSA FASE III",         "H12011033","Paterna",    "46980","Valencia",   "963 330 033","comunidad@santarosafase3.es",9),
    ("PANIFACTUM S.L. (PANADERÍA ARTESANA)", "B12011034","Catarroja",   "46470","Valencia",   "963 340 034","panaderia@panifactum.es", 10),
    ("IMPORTACIONES ASIÁTICA TRADING S.L.",   "B12011035","Picassent",  "46220","Valencia",   "963 350 035","trading@asiatica.es",     9),
    ("CLUB NÁUTICO CULLERA",                  "G12011036","Cullera",    "46400","Valencia",   "961 360 036","mantenimiento@nauticocullera.es",9),
    ("TORRES GÓMEZ, RAFAEL",                  "07850037U","Alaquàs",    "46970","Valencia",   "654 370 037","rafaeltg@gmail.com",      9),
    ("FINCA AGROECOLÓGICA LA HUERTA",         "B12011038","Sueca",      "46412","Valencia",   "962 380 038","finca@lahuerta.es",       10),
    ("ADMINISTRACIONES DE FINCAS REYES S.L.", "B12011039","Valencia",   "46005","Valencia",   "963 390 039","fincas@reyes.com",        9),
    ("CONSTRUCCIONES Y REFORMAS ALBA",        "B12011040","Torrent",    "46901","Valencia",   "963 400 040","alba@reformas.es",        10),
    ("JIMÉNEZ CASTILLO, DOLORES",             "18960041V","Xirivella",  "46950","Valencia",   "663 410 041","djc@hotmail.com",         9),
    ("RESIDENCIAL MIRADOR DEL MAR FASE I",    "H12011042","Gandia",     "46730","Valencia",   "962 420 042","residencial@miradordel.com",9),
    ("TALLERES CARROCERÍA BENET S.L.",        "B12011043","Algemesí",   "46680","Valencia",   "963 430 043","taller@benet.es",         10),
    ("EMPRESA MUNICIPAL AGUAS BENAGUASIL",    "M12011044","Benaguasil",  "46180","Valencia",  "963 440 044","aguas@benaguasil.es",     9),
    ("CENTRO SALUD TORRENT NORTE",            "Q12011045","Torrent",    "46900","Valencia",   "963 450 045","centrosalud@torrentnorte.es",9),
    ("VIVES SALES, PABLO",                    "29070046W","Riba-roja",  "46190","Valencia",   "672 460 046","pvs@gmail.com",           10),
    ("HOTEL RESTAURANT MAS DE CANICATTÍ",     "B12011047","Xàtiva",     "46800","Valencia",   "962 470 047","hotel@mascanicat.com",    9),
    ("CONGELADOS Y DISTRIBUCIÓN FRÍA S.L.",   "B12011048","Almusafes",  "46440","Valencia",   "961 480 048","fria@congelados.es",      9),
    ("FERNÁNDEZ BLANCO, ROSA MARIA",          "40180049X","Paiporta",   "46200","Valencia",   "681 490 049","rmfb@yahoo.com",          10),
    ("CLÍNICA ESTÉTICA DOCTORA SANZ",         "B12011050","Valencia",   "46007","Valencia",   "963 500 050","estetica@drazsanz.com",   9),
]
