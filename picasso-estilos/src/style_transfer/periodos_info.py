"""Fichas de cada periodo para explicar las transferencias a personas sin formacion en arte.
'no_reproduce' dice con honestidad que rasgos del periodo NO puede copiar la transferencia de estilo
(que solo cambia color y textura, no la composicion ni el dibujo)."""

PERIODOS = {
    "00_temprano": dict(
        nombre="Formación", anios="1881–1900",
        lugares="Málaga, A Coruña, Barcelona y Madrid",
        contexto="Picasso es niño y adolescente. Su padre, José Ruiz Blasco, es profesor de dibujo y lo forma "
                 "en la tradición académica: copiar yesos, dominar la anatomía y la perspectiva.",
        rasgos="Dibujo y modelado realistas, colores terrosos (ocres, marrones, grises cálidos), luz de taller. "
               "Retratos de familia, escenas religiosas y de costumbres.",
        obras="«La primera comunión» (1896), «Ciencia y caridad» (1897)",
        no_reproduce="El dibujo académico preciso y la perspectiva correcta: eso está en la composición, "
                     "y el algoritmo conserva la composición de la obra original."),
    "01_azul": dict(
        nombre="Período Azul", anios="1901–1904",
        lugares="Barcelona y París",
        contexto="Tras el suicidio de su amigo Carles Casagemas en 1901, Picasso pinta la tristeza, la pobreza "
                 "y la soledad. Vive con muy poco dinero.",
        rasgos="Casi todo en azules y azul verdoso, colores fríos y apagados. Figuras alargadas y delgadas "
               "(influencia de El Greco): mendigos, ciegos, madres pobres, músicos callejeros.",
        obras="«La vida» (1903), «El viejo guitarrista» (1903–1904)",
        no_reproduce="El alargamiento de las figuras y los temas de pobreza: el algoritmo trae el tono azul "
                     "y la pincelada, pero no cambia las proporciones de los cuerpos."),
    "02_rosa": dict(
        nombre="Período Rosa", anios="1905–1906",
        lugares="París (el taller del Bateau-Lavoir, en Montmartre)",
        contexto="Empieza su relación con Fernande Olivier y su ánimo se vuelve más sereno. Frecuenta el circo.",
        rasgos="Rosas, ocres y tierras cálidas, luz suave. Acróbatas, arlequines y saltimbanquis, "
               "con un dibujo delicado.",
        obras="«Familia de saltimbanquis» (1905), «Muchacho con pipa» (1905)",
        no_reproduce="Los temas de circo y la delicadeza del dibujo; solo se transfiere la paleta cálida "
                     "y la textura de la pintura."),
    "03_iberico_africano": dict(
        nombre="Período ibérico y africano", anios="1907–1908",
        lugares="París",
        contexto="Le impactan la escultura ibérica antigua y las máscaras africanas que ve en los museos. "
                 "Pinta «Les Demoiselles d'Avignon» (1907), que rompe con la forma tradicional de pintar el cuerpo.",
        rasgos="Rostros como máscaras, formas angulosas, volúmenes marcados con rayas paralelas, "
               "colores ladrillo, ocre y rosa.",
        obras="«Les Demoiselles d'Avignon» (1907)",
        no_reproduce="Los rostros-máscara y la deformación angulosa del cuerpo: son cambios de forma, "
                     "no de color, y el algoritmo no los produce."),
    "04_cubismo_analitico": dict(
        nombre="Cubismo analítico", anios="1909–1912",
        lugares="París (y veranos en Horta de Sant Joan, Cadaqués, Céret)",
        contexto="Trabaja casi a diario con Georges Braque. Juntos inventan el cubismo: pintar un objeto "
                 "desde varios puntos de vista a la vez.",
        rasgos="Los objetos se rompen en muchas facetas pequeñas. Paleta casi monocroma de marrones, grises "
               "y ocres, para que el color no distraiga de la forma.",
        obras="«Retrato de Ambroise Vollard» (1910)",
        no_reproduce="La fragmentación en facetas, que es lo más importante del período. La transferencia "
                     "solo trae la paleta parda y la textura; la obra no se vuelve cubista de verdad."),
    "05_cubismo_sintetico": dict(
        nombre="Cubismo sintético", anios="1913–1919",
        lugares="París; Roma en 1917",
        contexto="Desde 1912 incorpora el collage: pega papel pintado, periódico y partituras. Llega la Primera "
                 "Guerra Mundial (1914–1918) y en 1917 diseña decorados para los Ballets Rusos («Parade»).",
        rasgos="Planos grandes y lisos que se superponen, colores más vivos que en el cubismo analítico, "
               "letras y texturas imitadas (madera, papel).",
        obras="Collages y naturalezas muertas con guitarra y botella",
        no_reproduce="El recorte en planos y el collage; el algoritmo trae colores más vivos y algo de la "
                     "textura plana, pero no reorganiza la imagen en planos."),
    "06_neoclasico": dict(
        nombre="Período neoclásico", anios="1920–1924",
        lugares="París y veranos en la costa francesa (Fontainebleau, Juan-les-Pins)",
        contexto="Después de la guerra hay un «retorno al orden» en el arte europeo. Picasso se casa con la "
                 "bailarina Olga Khokhlova (1918) y nace su hijo Paulo (1921).",
        rasgos="Figuras monumentales y pesadas, como esculturas clásicas; tonos tierra, rosados y pasteles; "
               "temas mediterráneos y mitológicos.",
        obras="«Tres mujeres en la fuente» (1921)",
        no_reproduce="El volumen escultórico de las figuras; solo se transfiere la paleta y la textura."),
    "07_surrealista": dict(
        nombre="Período surrealista", anios="1925–1936",
        lugares="París y el castillo de Boisgeloup (desde 1930)",
        contexto="Se acerca al grupo surrealista, que explora los sueños y el inconsciente. Desde 1927 "
                 "Marie-Thérèse Walter es su modelo principal.",
        rasgos="Cuerpos deformados y blandos (formas «biomórficas»), contornos negros gruesos, curvas, "
               "colores planos e intensos.",
        obras="«Las tres bailarinas» (1925), «El sueño» (1932)",
        no_reproduce="La deformación de los cuerpos y los contornos gruesos como dibujo; el algoritmo "
                     "toma los colores intensos y parte de los trazos oscuros."),
    "08_guerra": dict(
        nombre="Años de guerra", anios="1937–1945",
        lugares="París (ocupada por Alemania entre 1940 y 1944) y Royan",
        contexto="La Guerra Civil española y el bombardeo de Gernika (1937) lo llevan a pintar «Guernica». "
                 "Después llega la Segunda Guerra Mundial. Dora Maar es su compañera en estos años.",
        rasgos="Paleta sombría (negros, grises, ocres apagados), contrastes duros, formas angulosas y "
               "cortantes, rostros de dolor, naturalezas muertas con calaveras.",
        obras="«Guernica» (1937), «Mujer que llora» (1937)",
        no_reproduce="Las formas cortantes y los rostros de dolor; se transfieren el oscurecimiento, "
                     "los contrastes y la textura áspera."),
    "09_tardio": dict(
        nombre="Período tardío", anios="1946–1973",
        lugares="Antibes, Vallauris, Cannes, Vauvenargues y Mougins (sur de Francia)",
        contexto="Vive junto al Mediterráneo con Françoise Gilot y después con Jacqueline Roque (se casan en "
                 "1961). Hace cerámica en Vallauris y pinta series enteras sobre obras de otros maestros, como "
                 "«Las Meninas» de Velázquez (1957). Muere en Mougins en 1973.",
        rasgos="Pincelada rápida, suelta y gestual; colores luminosos; trazos negros gruesos; "
               "muchas variaciones sobre un mismo tema.",
        obras="Serie «Las Meninas» (1957), mosqueteros y parejas (años 60)",
        no_reproduce="La reinterpretación de obras maestras y la composición gestual; se transfieren "
                     "los colores luminosos y la pincelada suelta."),
}
