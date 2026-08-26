# Apuestas-Trading

Análisis cuantitativo de estrategias de apuesta: qué funciona, qué no, y por qué —
todo verificado con simulación, no con afirmaciones.

> **📄 Empieza por [`docs/ESTRATEGIA_ESPERANZA_POSITIVA.md`](docs/ESTRATEGIA_ESPERANZA_POSITIVA.md)**
> — el razonamiento completo: por qué ninguna progresión puede dar esperanza
> positiva (con demostración), y cuál es la estructura que sí la da (criterio de
> Kelly sobre una ventaja real), incluyendo cómo validar que esa ventaja existe.

## Contenido

| Módulo | Qué hace |
|---|---|
| `roulette_fibonacci/strategy.py` | Fibonacci acotada a 6 pasos (ver abajo) |
| `roulette_fibonacci/labouchere.py` | Sistema de cancelación: objetivo +1 unidad por sesión |
| `roulette_fibonacci/campaign.py` | Simula acumular +1u por sesión con límite de mesa y banca |
| `roulette_fibonacci/ev_proof.py` | Demuestra que 6 sistemas distintos convergen al mismo −2.7% |
| `apuestas/edge.py` | De dónde sale la ventaja: precio vs probabilidad real, quitar el *vig* |
| `apuestas/kelly.py` | Dimensionamiento correcto **cuando existe ventaja** |
| `apuestas/wheel_bias.py` | El único camino +EV real en ruleta: detectar una rueda sesgada |
| `apuestas/value.py` | **Detector de valor:** cuotas reales → sin comisión → EV → apuesta |
| `apuestas/tracker.py` | **Registro histórico** y validación estadística de la ventaja |
| `apuestas/clv_power.py` | Por qué el CLV detecta la ventaja ~128x antes que el beneficio |

Ver [`docs/DETECCION_DE_VALOR.md`](docs/DETECCION_DE_VALOR.md) para el flujo completo.

```bash
python3 -m pytest tests/ -q
python3 -m roulette_fibonacci.ev_proof          # el teorema, empíricamente
python3 -m roulette_fibonacci.campaign          # el plan "+1u por sesión", medido
python3 -m apuestas.kelly --p 0.55 --odds 2.0   # crecimiento compuesto con ventaja real
python3 -m apuestas.wheel_bias                  # cuántos giros para probar un sesgo

# Flujo de detección de valor
python3 -m apuestas.value examples/mercados.json --reference pinnacle --min-ev 0.02
python3 -m apuestas.tracker add --event "..." --selection "..." --book casa_b \
    --odds 2.35 --p 0.4615 --stake 31.34
python3 -m apuestas.tracker settle b00001 won --closing-odds 2.20
python3 -m apuestas.tracker report
python3 -m apuestas.clv_power                   # ROI vs CLV: velocidad de detección
```

---

## Fibonacci acotada para apuestas simples de ruleta

Implementación y simulación de la primera estrategia planteada: apostar a chances
simples (rojo/negro, par/impar, 1-18/19-36 — pagan 1 a 1, tu apuesta se
duplica si aciertas) usando la secuencia de Fibonacci en lugar de Martingala,
con el avance **tope en 6 pérdidas** para no dejar crecer la apuesta sin
límite.

## Cómo funciona la progresión

- Secuencia base: `1, 1, 2, 3, 5, 8` (6 términos).
- **Pierdes** → avanzas un paso en la secuencia (subes de apuesta).
- **Ganas** → retrocedes **dos** pasos (no vuelves directo a 1 como en
  Martingala). Esto es lo estándar en Fibonacci: como `fib(n) = fib(n-1) +
  fib(n-2)`, una victoria en el paso `n` alcanza para cubrir exactamente las
  dos pérdidas anteriores, no toda la racha.
- Al llegar a la 6ª pérdida consecutiva (apuesta = 8 unidades) la apuesta se
  **congela ahí**: si sigues perdiendo, sigues apostando 8, no 13, 21, 34...

Esto está implementado en `roulette_fibonacci/strategy.py` (`FibonacciStrategy`),
con tests en `tests/test_strategy.py` que verifican la progresión exacta
(`1,1,2,3,5,8,8,8,...` en pérdidas y el retroceso de dos pasos en victorias).

## Lo importante: qué SÍ y qué NO logra este sistema

Ninguna gestión de apuestas cambia la probabilidad de cada tirada. En una
ruleta europea (un solo cero) una chance simple gana con probabilidad
`18/37 ≈ 48.65%`, y la ventaja de la casa (~2.7%) está incorporada en cada
giro sin importar cuánto apuestes ni en qué orden.

Lo que Fibonacci-con-tope sí cambia es la **forma del riesgo**:

- Frente a Martingala, la apuesta crece mucho más lento (progresión aditiva,
  no exponencial), así que una racha larga de pérdidas te cuesta bastante
  menos antes de tocar el límite de mesa o tu bankroll.
- El tope en 6 pérdidas evita el crecimiento descontrolado, pero tiene un
  costo: una vez congelado en 8, cada pérdida adicional ya no la "absorbe" la
  progresión — se acumula linealmente. Y el retroceso de dos pasos tras una
  victoria deja de recuperar toda la racha; solo cubre las dos últimas
  pérdidas de 8.
- Resultado neto: en rachas largas, el sistema **no garantiza recuperar lo
  perdido**, solo amortigua qué tan rápido se dispara la exposición.

## Simulación Monte Carlo (números reales, no teoría)

`roulette_fibonacci/simulate.py` corre miles de sesiones simuladas contra una
ruleta real (probabilidades exactas de 18/37 o 18/38), con unidad=1,
take-profit=+50, stop-loss=-100, hasta 5000 giros por sesión:

```
$ python3 -m roulette_fibonacci.simulate --wheel european --sessions 20000 \
    --unit 1 --bankroll 200 --take-profit 50 --stop-loss 100 --max-spins 5000 --seed 42

Wheel: european (win prob per spin: 0.4865)
Sesiones que terminan en ganancia: 39.2%
Ganancia media por sesión: -43.07 unidades
Ganancia mediana por sesión: -101.00 unidades
Mejor / peor sesión: 50.00 / -107.00 unidades
Drawdown medio dentro de una sesión: 92.98 unidades
Motivo de cierre: {'stop_loss': 12140, 'take_profit': 7843, 'max_spins': 17}
```

Con ruleta americana (doble cero, `18/38`) empeora bastante: solo 18.1% de
sesiones terminan en ganancia y la media cae a -75 unidades.

**Lectura honesta del resultado:** el objetivo de +50 se toca el 39% de las
veces, pero el stop-loss de -100 se toca el 61% del tiempo — la asimetría del
objetivo (ganar poco, arriesgar el doble) hace que, aun con más sesiones
"ganadoras" que perdedoras en frecuencia de toque, el valor esperado sea
negativo. Esto es consistente con cualquier sistema de progresión sobre un
juego con ventaja de la casa: no hay combinación de tamaños de apuesta que
convierta un juego con EV negativo por tirada en uno con EV positivo.

## Uso

```bash
pip install pytest   # solo para correr los tests
python3 -m pytest tests/ -q

python3 -m roulette_fibonacci.simulate --help
python3 -m roulette_fibonacci.simulate --wheel european --sessions 5000 \
    --unit 1 --max-steps 6 --bankroll 200 --take-profit 50 --stop-loss 100
```

Parámetros ajustables sin tocar código: unidad de apuesta (`--unit`), tope de
la progresión (`--max-steps`), objetivo de ganancia y stop-loss de la sesión,
y tipo de rueda (`--wheel european|american`).

## Para qué sirve esto en la práctica

Si buscas **gestión de riesgo / disciplina de sesión** (limitar cuánto puedes
perder en una mala racha, saber cuándo parar), esta estructura es razonable
y mejor que Martingala en cuanto a velocidad de crecimiento de la apuesta.
Si buscas una forma de **ganarle a la ruleta a largo plazo**, ningún sistema
de progresión —Fibonacci, Martingala, D'Alembert— lo consigue: la simulación
de arriba lo muestra con números, no como advertencia genérica.
