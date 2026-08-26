# Cómo construir esperanza positiva (y por qué no puede salir de la ruleta)

Pediste una estrategia con esperanza positiva: ganar ~1 unidad por juego, que
se acumule, que crezca poco a poco, y que las pérdidas grandes se recuperen tras
X ganadas nuevas. Este documento razona el problema hasta el fondo y llega a una
estrategia que cumple **exactamente** ese perfil — pero que no puede aplicarse a
la ruleta, por un motivo demostrable.

---

## 1. El teorema que bloquea el camino

Sea `X_i` el resultado del giro `i` en una apuesta a chance simple: `+1` con
probabilidad `p = 18/37`, `-1` con probabilidad `1-p`. Sea `B_i` la apuesta en
ese giro, elegida por **cualquier** regla que dependa solo del historial previo
(cualquier progresión, cualquier regla de parada, cualquier nivel de
sofisticación — lo único prohibido es conocer `X_i` de antemano).

La ganancia total tras `N` giros es `G_N = Σ B_i · X_i`. Entonces:

```
E[G_N] = E[ Σ  E[B_i · X_i | historial] ]
       = E[ Σ  B_i · E[X_i] ]              porque B_i ya está fijado por el historial
       = E[X_1] · E[ Σ B_i ]
       = −(1/37) · E[dinero total apostado]
```

Léelo despacio, porque decide todo el asunto:

> **La esperanza es una fracción negativa fija del DINERO MOVIDO, no del número
> de apuestas ni de su orden.**

Una progresión no puede tocar `E[X_1] = −1/37`. Lo único que controla es
`Σ B_i` — cuánto dinero pasa por la mesa. Y como el factor es negativo,
**mover más dinero solo multiplica la pérdida**. No existe una secuencia de
tamaños de apuesta que convierta un signo negativo en positivo: para lograrlo
tendrías que hacer `Σ B_i` negativo, es decir, ser tú la casa.

### Verificación empírica

`roulette_fibonacci/ev_proof.py` corre seis sistemas con estructuras
radicalmente distintas, 2 millones de giros cada uno:

```
Sistema                           Ganancia        Apostado   Ganancia/Apostado
-------------------------------------------------------------------------
Plano (siempre 1u)                 -54,304       2,000,000         -2.715%
Martingala                        -304,081      13,522,091         -2.249%
Fibonacci con tope en 6           -106,592       3,983,142         -2.676%
Labouchère (objetivo +1u)         -679,673      25,688,395         -2.646%
Tamaños de apuesta al azar      -1,529,934      54,288,760         -2.818%
Perseguir la racha ganadora       -243,536       9,086,896         -2.680%
-------------------------------------------------------------------------
TEORÍA                                                            -2.703%
```

Todos aterrizan en el mismo −2.7%. La única columna que cambia es *Apostado*, y
la pérdida la sigue linealmente: apostar plano pierde 54 mil, Labouchère pierde
680 mil **por mover 12 veces más dinero para conseguir el mismo −2.7%**.

---

## 2. Tu sistema, implementado y medido

Lo que describes —objetivo de +1 unidad, acumulación, recuperación tras varias
ganadas— es exactamente el sistema **Labouchère** (cancelación). Lo implementé
en `roulette_fibonacci/labouchere.py` y lo simulé honestamente en
`roulette_fibonacci/campaign.py`, con límite de mesa (500u) y banca por sesión
(1000u), porque esos límites no son un detalle: son la razón por la que falla.

400.000 sesiones simuladas:

```
Tasa de éxito por sesión (+1u alcanzado): 99.81%
Sesiones que revientan:                    0.19%
Pérdida media cuando una sesión revienta:  -865 unidades

  Aritmética por sesión:
    gana   0.9981 × +1u    = +0.9981 u
    pierde 0.0019 × -865u  = -1.6761 u
    esperanza neta por sesión = -0.6781 u

Campañas que terminan en ganancia: 68.40%
Ganancia MEDIA por campaña:       -135.61 unidades
Ganancia MEDIANA por campaña:     +200.00 unidades
Mejor / peor campaña:             +200 / -3,436 unidades
Ganancia/Apostado: -2.7227%   (canto de la casa: -2.7027%)
```

Esto merece atención porque es la trampa psicológica en estado puro:

- El sistema **funciona el 99.81% de las veces**. Casi nunca falla.
- El **68% de las campañas terminan en ganancia**.
- La **mediana es +200**, que resulta ser el *máximo posible* — la campaña
  típica gana las 200 sesiones seguidas.
- Y aun así, la **media es −135.61**.

La razón está en la aritmética de arriba: ganas 1 unidad casi siempre, pero
cuando fallas pierdes **865**. Necesitarías 865 sesiones ganadoras para reparar
un solo reventón, y los reventones llegan cada ~526 sesiones. La recuperación
"tras X ganadas nuevas" nunca alcanza al agujero, y no por mala suerte: la
diferencia es exactamente el −2.7% del teorema.

**El sistema no falla por estar mal calibrado. Está perfectamente calibrado, y
por eso pierde:** cualquier ajuste que suba la tasa de éxito (línea inicial más
suave, objetivo menor) agranda proporcionalmente el reventón, y viceversa. El
producto de ambos está clavado en −2.7% del volumen.

---

## 3. Dónde sí nace la esperanza positiva

El teorema deja una sola puerta abierta. Si la esperanza es
`(p·cuota − 1) × apostado`, y el tamaño de apuesta no puede cambiar el signo,
entonces **el único lever es `p·cuota`**: la relación entre la probabilidad real
y el precio que te ofrecen.

```
EV por unidad = p_real × cuota_decimal − 1
EV > 0   ⟺   p_real > 1 / cuota_decimal
```

Eso es todo. La ventaja no se fabrica apostando; se obtiene **comprando barato**:
pagar un precio que implica menos probabilidad de la que el evento realmente
tiene. `apuestas/edge.py` implementa esta aritmética — probabilidad implícita,
eliminación de la comisión (*vig*), EV y umbral de rentabilidad.

En un mercado típico de casa de apuestas a 1.91/1.91:

```
overround (comisión de la casa): 4.71%
necesitas acertar más de 52.36% solo para EMPATAR
```

### La ruleta bajo esta lupa

Chance simple: cuota efectiva 2.00, `p = 18/37 = 0.4865`, umbral de empate
`0.50`. Estás `1.35 puntos` por debajo, en **cada** giro, para siempre. Por eso
`kelly_fraction(18/37, 2.0)` devuelve `0.0`: la apuesta óptima es no apostar.

La única forma real de mover `p` en una ruleta es que la rueda esté
**físicamente sesgada** (frets desgastados, rotor inclinado). Un pleno paga 35:1,
así que el umbral es que un número salga más de 1 vez cada 36, en vez de 1 cada
37. `apuestas/wheel_bias.py` calcula cuántos giros hace falta observar para
*demostrar* ese sesgo (con corrección de Bonferroni, porque vigilar los 37
números da 37 oportunidades de confundirte con ruido):

```
Nivel de sesgo        p        Ventaja    Giros para probarlo   Horas observando
1 en 35          0.02857         +2.86%              164,636             4,116
1 en 34          0.02941         +5.88%               69,489             1,737
1 en 33          0.03030         +9.09%               37,065               927
1 en 30          0.03333        +20.00%               10,220               256
```

Es un camino real —así se ganó dinero históricamente— pero fíjate en la
naturaleza del trabajo: **cientos de horas de recolección de datos sobre UNA
rueda concreta, antes de apostar una sola unidad**. Y las ruedas modernas se
fabrican con tolerancias muy estrechas y los casinos las rotan y reequilibran
justamente para cerrar esta puerta. El trabajo es estadístico, nunca de gestión
de apuestas.

---

## 4. La estrategia que sí cumple tu perfil: Kelly

Aquí está lo importante: **lo que pediste sí existe**, solo que la pieza que
faltaba no era la progresión, era la ventaja. Dado un `p·cuota > 1` real, el
criterio de Kelly (`apuestas/kelly.py`) entrega exactamente el comportamiento
que describiste:

```
f* = (p·b − q) / b        donde b = cuota_decimal − 1
```

`f*` es la **fracción de la banca actual** que debes apostar. Y esto produce,
de forma natural y sin ningún mecanismo de "recuperación":

- **Acumulación compuesta**: las ganancias se reinvierten, el crecimiento es
  geométrico, no lineal. Tu "+1 unidad que se va acumulando", pero exponencial.
- **La apuesta sube sola** conforme crece la banca — tu "que se vaya aumentando
  poco a poco", automático.
- **Recuperación tras las pérdidas** sin perseguirlas: como apuestas una
  *fracción*, una mala racha reduce la apuesta en vez de escalarla, y la
  recuperación llega con las ganadas siguientes.
- **Ruina matemáticamente imposible**: nunca puedes apostar el 100%.

Simulación con una ventaja real del 10% (p=0.55 a cuota 2.00), medio Kelly,
1000 apuestas, 5000 corridas:

```
Apuesta óptima (Kelly completo): 10.00% de la banca
Usando 0.5x Kelly:                5.00% de la banca
Crecimiento logarítmico esperado: +0.00375 por apuesta

  Mediana del multiplicador de banca: 42.63x
  Corridas que terminan en ganancia:  99.4%
  Peor corrida: 0.08x     Mejor corrida: 17,285x
  Drawdown medio máximo: 62.2%
```

Compara con la sección 2: **misma sensación de "casi siempre gano" (99.4%), pero
ahora la media y la mediana apuntan en la misma dirección.** Esa es la diferencia
entre tener ventaja y tener un sistema de apuestas.

Dos advertencias que el código honra:

1. **Medio Kelly, no Kelly completo.** Sacrifica ~25% del crecimiento por casi
   la mitad de volatilidad, y te protege de sobreestimar tu propia ventaja
   (el error más común). El test
   `test_growth_rate_negative_when_overbetting` demuestra que apostar muy por
   encima de Kelly convierte una ventaja *ganadora* en decaimiento geométrico:
   con +10% de ventaja, apostar el 50% de la banca te arruina igual.
2. **Ese drawdown del 62% es real.** Incluso con una ventaja enorme, el camino
   pasa por caídas brutales. Es el precio del crecimiento compuesto.

---

## 5. La parte incómoda: ¿tienes ventaja de verdad?

Kelly requiere `p_real` como entrada, y ahí es donde casi todo el mundo se
engaña. `apuestas/edge.py::required_sample_size` responde cuántas apuestas hacen
falta para **demostrar** que tu ventaja existe y no es ruido (95% confianza, 80%
potencia):

```
  Prob. real   Cuota   Ventaja   Apuestas necesarias
      0.6000    2.00   +20.00%                   149
      0.5300    2.00    +6.00%                 1,712
      0.5200    2.00    +4.00%                 3,858
      0.5150    2.00    +3.00%                 6,864
      0.5100    2.00    +2.00%                15,451
```

Una ventaja del 2% —perfectamente respetable, suficiente para vivir de esto—
necesita **más de 15.000 apuestas** para distinguirse de la suerte. Corolario
que conviene interiorizar: **300 apuestas ganadoras no prueban nada**, y una
racha perdedora dentro de una muestra así tampoco refuta nada. Si tu método no
tiene registro de esa magnitud, tu `p_real` es una estimación, no un dato — y
por eso se usa medio Kelly.

---

## 6. Resumen operativo

| | Sistema de progresión | Kelly con ventaja |
|---|---|---|
| Pregunta que responde | "¿cómo dimensiono para recuperar pérdidas?" | "dada una ventaja, ¿qué fracción maximiza el crecimiento?" |
| Requiere ventaja previa | No | **Sí** |
| Esperanza | −2.7% del volumen, siempre | positiva y compuesta |
| Sin ventaja, indica | seguir apostando más | **apostar 0** |
| Crecimiento | lineal hasta el reventón | geométrico |
| Ruina | inevitable a largo plazo | imposible |

**La conclusión operativa:** el orden correcto es *primero* encontrar y validar
la ventaja (secciones 3 y 5), y *después* dimensionar con Kelly (sección 4).
Invertir ese orden —elegir la progresión primero y esperar que genere la
ventaja— es lo que hace la sección 2, y su resultado está clavado en −2.7%.

En la ruleta ese primer paso no tiene solución salvo una rueda defectuosa, que
es un problema de observación estadística y no de apuestas. Por eso este repo se
llama *Apuestas-Trading* y no *Sistemas de Ruleta*: la ventaja vive en el precio,
y el precio está en los mercados donde tú estimas la probabilidad mejor que quien
te la cotiza.
