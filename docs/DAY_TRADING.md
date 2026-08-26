# Day trading: Martingala + análisis técnico, medido con datos reales

Pediste combinar Martingala con conocimiento técnico/fundamental para tener
"una verdadera mínima ventaja". Aquí está medido con precios reales de mercado
(Yahoo Finance, sin API de pago), no con teoría. Dos preguntas separadas:

1. ¿Ayuda Martingala en trading? — **No, y aquí es peor que en ruleta.**
2. ¿Da ventaja real el análisis técnico? — depende, y hay que medirlo bien o
   te vas a engañar solo. Aquí está el marco para medirlo honestamente.

---

## 1. Por qué Martingala es MÁS peligrosa en trading que en ruleta

En ruleta, Martingala falla por el mismo motivo que cualquier progresión: la
esperanza es negativa por unidad apostada, siempre (`docs/ESTRATEGIA_ESPERANZA_POSITIVA.md`).
En trading falla por esa misma razón, **más otras dos que no existen en la
ruleta:**

**No hay límite de mesa.** Una apuesta de ruleta está topada por el límite de la
mesa. Una posición apalancada en trading solo está topada por tu capital y el
*margin call* de tu bróker — que llega sin avisar.

**Las tiradas de ruleta son independientes; los precios NO.** Una racha mala en
ruleta tiene que revertir tarde o temprano hacia el 48,65% de aciertos, porque
cada giro es independiente del anterior. Una **tendencia** de mercado no tiene
esa garantía: el precio puede seguir moviéndose en tu contra semanas enteras,
porque el movimiento de hoy y el de mañana no son sorteos independientes de la
misma distribución fija. Esto es exactamente lo que ha reventado cuentas reales
de day traders con bots "grid" en forex: cada nueva entrada dobla la exposición
dentro de una tendencia que no tiene ninguna obligación de girar antes de que la
cuenta desaparezca.

### Medido con un mercado bajista real

Simulé "comprar la caída, doblar cada vez que sigue bajando" —Martingala
aplicada a trading, también llamada estrategia *grid*— contra el desplome real
de **QQQ en 2022** (-33,5% de máximo a mínimo, un mercado bajista real, no un
caso extremo inventado):

```
$ python3 -m trading.martingale_demo --symbol QQQ --start 2021-11-19 --end 2022-10-13 \
    --initial-position 5 --add-on-drop 0.03 --max-leverage 10

QQQ, 2021-11-19 -> 2022-10-13  (226 dias)
Caida maxima real en el periodo: -33.5%

Estrategia                       Capital final   Exposicion pico
----------------------------------------------------------------
Posicion fija (sin doblar)               98.33            100.00
Martingala / grid                    LIQUIDADA           1244.72   (dia 128: 2022-05-25)
```

**La cuenta explota el 25 de mayo de 2022 — meses antes de que el mercado
tocara fondo en octubre.** No hizo falta que cayera un 33,5%; con doblar cada
3% de caída, a los 128 días la exposición ya era 12,4 veces el capital, y el
bróker cierra la cuenta por *margin call*. La posición fija, sin doblar, perdió
solo 1,67 de 100 en el mismo periodo.

Con parámetros algo menos agresivos (doblar cada 5% en vez de cada 3%) sobrevive
esta vez concreta, pero termina con 43,66 de 100 y llegó a estar 7,2 veces
apalancada — a un tramo bajista algo más largo de distancia de la liquidación.
Prueba distintos parámetros tú mismo: `python3 -m trading.martingale_demo --help`.

**Conclusión de esta parte: no incorpores Martingala a ninguna estrategia de
trading.** No solo no da ventaja (igual que en ruleta) — además el riesgo no
tiene techo, y el mecanismo que lo detona (una tendencia sostenida) es
precisamente lo que los mercados sí hacen y la ruleta nunca hace.

---

## 2. Análisis técnico: el marco para medir si hay ventaja de verdad

Aquí sí hay una diferencia real con la ruleta: en la ruleta no existe ninguna
información que prediga el próximo número (salvo un defecto físico de la
rueda). En los mercados, sí puede existir información real — pero **la inmensa
mayoría de patrones técnicos que "parecen funcionar" son sobreajuste (curve
fitting)**: se ajustan tan bien al pasado como un traje a medida, y no sirven
para nada en datos nuevos. Por eso el marco de validación es la mitad del
trabajo, no un detalle.

### El motor de backtest (`trading/backtest.py`)

Dos reglas que evitan que un backtest mienta sin que te des cuenta:

- **La señal de hoy solo puede ganar el retorno de mañana**, nunca el de hoy
  mismo (mirar el futuro sin querer es el error más común y el que más infla
  resultados falsos).
- **Se cobra coste cada vez que cambias de posición** (spread + comisión +
  deslizamiento). Una estrategia que parece ganar sin contar costes casi
  siempre deja de ganar en cuanto se los descuentas.

### La validación (`trading/validation.py`)

El equivalente aquí al CLV de las apuestas deportivas es partir el histórico en
dos mitades: ajustas/miras en la primera, compruebas en la **segunda, que la
estrategia nunca vio**. Si algo funciona solo en la primera mitad, es
sobreajuste, no ventaja.

### Resultado real: dos estrategias técnicas de libro, sobre SPY y AAPL, 5 años

```
$ python3 -m trading.validation SPY "SMA 20/50"
$ python3 -m trading.validation AAPL "RSI 14"
```

| Estrategia | Activo | 2a mitad (out-of-sample) | Comprar-y-mantener | p-valor |
|---|---|---|---|---|
| Media móvil 20/50 | SPY | +27.5% | **+51.3%** | 0.060 |
| RSI 14 (30/70) | SPY | +21.4% | **+51.3%** | 0.114 |
| Media móvil 20/50 | AAPL | +33.2% | **+72.6%** | 0.142 |
| RSI 14 (30/70) | AAPL | +14.9% | **+72.6%** | 0.278 |

**Las cuatro pierden contra simplemente comprar y mantener**, una vez
descontados los costes, en los datos que la estrategia no vio al calibrarse.
Esto no es un fallo del código: es el resultado honesto y esperado. Coincide
con lo que muestran décadas de estudios académicos sobre reglas técnicas
simples en mercados líquidos y eficientes como estos: rara vez sobreviven
fuera de la muestra con la que se afinaron.

**Esto no significa que el análisis técnico sea inútil en general** — significa
que reglas de libro de texto sobre los activos más seguidos del mundo (S&P 500,
Apple) no tienen ventaja demostrable después de costes. Es exactamente donde
esperarías NO encontrar ventaja: miles de gestores profesionales ya explotaron
cualquier patrón obvio en esos activos hace años.

### Dónde SÍ tendría sentido buscar

Aplicando la misma lógica que en apuestas (la ventaja vive donde el mercado
está menos vigilado, no en el activo más popular):

- **Activos con menos seguimiento profesional**: small caps, mercados
  emergentes, criptomonedas de baja capitalización — el precio de la
  ineficiencia es más riesgo y menos liquidez.
- **Ventaja de información real**, no de patrón de precio: conocer un sector
  a fondo, datos alternativos, análisis fundamental genuino sobre algo que el
  consenso aún no ha incorporado. Esto es investigación, no un indicador.
- **Marcos de tiempo y activos donde tú tengas de verdad un borde**, no donde
  "parece que debería funcionar".

Y en cualquiera de esos casos, el proceso es el mismo que ya montamos:
backtest sin *lookahead*, con costes reales, validado fuera de muestra, y
**registrado en vivo** para confirmar que el resultado sobrevive con dinero
real — el mismo principio que el CLV en apuestas, aplicado a trading (el
equivalente sería comparar tu precio de entrada contra el VWAP del día, o
simplemente llevar el registro de operaciones con `apuestas/tracker.py`, que
ya sirve para esto sin cambiar una línea).

---

## Resumen

| | Martingala en trading | Análisis técnico simple (SMA/RSI de libro) |
|---|---|---|
| ¿Da ventaja? | No, nunca | Medido: no, en SPY/AAPL a 5 años |
| Riesgo extra vs. ruleta | Sin límite de mesa + tendencias persistentes | — |
| Qué hacer | No usarla, punto | Backtest sin *lookahead* + validación fuera de muestra antes de arriesgar nada |
| Dónde buscar ventaja real | — | Activos menos vigilados + información genuina, no patrones de precio |

**Antes de operar cualquier regla con dinero real: que pase la validación fuera
de muestra con el mismo rigor que el ejemplo de arriba.** Si no la pasa —como
las cuatro de la tabla— no es una estrategia, es una corazonada con gráficos.
