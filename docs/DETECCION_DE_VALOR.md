# Detección de valor: del precio real a la apuesta validada

Este es el módulo que implementa lo único que genera esperanza positiva: **pagar
menos de lo que algo vale**. No hay progresiones aquí. El flujo completo es:

```
cuotas reales  →  quitar comisión  →  comparar  →  dimensionar  →  registrar  →  validar
   (varias         (devig)           (¿hay        (Kelly)        (histórico)   (¿es real
    casas)                            valor?)                                   la ventaja?)
```

---

## 1. Quitar la comisión (*devig*)

Una casa nunca te da probabilidades: te da precios con su margen dentro. Un
mercado a 1.91 / 1.91 implica 52,36% + 52,36% = **104,71%**. Ese 4,71% sobrante
es la comisión, y hasta que no la quitas ningún número significa nada.

```python
from apuestas.value import devig
devig([1.91, 1.91])            # -> [0.5, 0.5]
```

Hay tres métodos implementados, y **la elección es una hipótesis, no un
detalle**:

| Método | Qué asume | Cuándo usarlo |
|---|---|---|
| `multiplicative` | la comisión es proporcional | por defecto, mercados a dos vías |
| `additive` | la comisión es un cargo plano por resultado | poco común, útil de contraste |
| `power` | la casa carga más margen al *longshot* | mercados desequilibrados |

En un mercado equilibrado los tres coinciden. En uno de 1.10 / 8.00 discrepan
**más que una ventaja típica**, así que ahí el método que elijas decide si ves
valor o no. Hay un test que fija justamente esa discrepancia.

## 2. Encontrar el valor

Dos formas de decidir la probabilidad "justa":

**(a) Contra las casas *sharp* — la práctica, sin modelar nada.**
La línea de una casa sharp (tipo Pinnacle), ya sin comisión, suele ser mejor
estimación de la probabilidad real que cualquier modelo que puedas construir al
principio. Buscas casas blandas que se desvíen de ella:

```bash
python3 -m apuestas.value examples/mercados.json --reference pinnacle --min-ev 0.02
```

```
  Seleccion                 Justa  Cuota justa    Mejor        Casa       EV
  ----------------------------------------------------------------------
  Local                    53.85%         1.86     1.80    pinnacle   -3.08%
  Visitante                46.15%         2.17     2.35      casa_b   +8.46%  <-- VALOR

  APUESTAS CON VALOR (medio Kelly):
    Visitante @ 2.35 en casa_b  |  EV +8.46%  |  apostar 3.13% de banca = 31.34
```

**(b) Contra tu propia estimación** — cuando de verdad sabes más que el mercado
sobre un nicho concreto:

```python
find_value(market, estimates={"Local": 0.60, "Visitante": 0.40})
```

El código exige que tus probabilidades **sumen 1**. Suena trivial y no lo es: es
el error más común al estimar a ojo, y produce "valor" fantasma en ambos lados
del mercado a la vez.

### Comparar precios vale más de lo que parece

El detector siempre toma **el mejor precio disponible** entre todas las casas.
Esto por sí solo vale ~1-2%, que es el tamaño de una ventaja respetable *antes*
de haber modelado nada. Apostar en una sola casa por comodidad regala esa
ventaja entera.

## 3. Dimensionar

Sale directo de `apuestas/kelly.py`: fracción de la banca, medio Kelly por
defecto. Fíjate en el ejemplo de arriba: un EV del +8,46% recomienda apostar el
**3,13%** de la banca, no "una unidad". Y el 1,67% de EV del tercer mercado
recomienda un 0,32%. La apuesta escala con la ventaja, no con la corazonada.

## 4. Registrar

```bash
python3 -m apuestas.tracker add --event "Liga menor J12" --selection "Visitante" \
    --book casa_b --odds 2.35 --p 0.4615 --stake 31.34

python3 -m apuestas.tracker settle b00001 won --closing-odds 2.20
```

Se guarda en CSV plano a propósito: debe sobrevivir a este código y poder
abrirse en cualquier hoja de cálculo. **Registra siempre la cuota de cierre** —
la sección siguiente explica por qué es el dato más valioso de todos.

## 5. Validar: el problema de las 15.000 apuestas, resuelto

Ya vimos que demostrar una ventaja del 2% **solo por beneficio** requiere ~15.000
apuestas. Es un obstáculo real: nadie quiere apostar tres años para descubrir si
su método funciona.

El **CLV (Closing Line Value)** lo esquiva. Mide si el precio que tomaste era
mejor que el precio final antes del comienzo. La línea de cierre es la mejor
estimación que el mercado produce, así que batirla de forma consistente
demuestra que valoras mejor que el mercado — y decisivamente, **el CLV no está
contaminado por si el balón entró o no**:

```
beneficio por apuesta:  +（cuota−1) o −1   →  desviación típica ~1,00
CLV por apuesta:        cuota / cierre     →  desviación típica ~0,04
```

Misma media, 25 veces menos ruido. Y el tamaño de muestra necesario escala con
el **cuadrado** de esa relación. `apuestas/clv_power.py` lo mide:

```
  Apuestas     Detecta por ROI     Detecta por CLV
--------------------------------------------------
        25               9.0%               98.0%
       100               9.3%              100.0%
     1,600              28.7%              100.0%
     3,200              49.0%              100.0%
    12,800              92.0%              100.0%

Mediana de apuestas hasta detectar la ventaja:
  por ROI: 3,200        por CLV: 25        (~128x antes)
```

Un historial simulado de 300 apuestas de un apostante con **ventaja real del 3%**
lo enseña en un solo informe:

```
  RESULTADO
    ROI:  +3.68%
  ¿ES REAL LA VENTAJA?
    ROI t-stat: +0.59   p-valor: 0.2773
    -> compatible con azar: sigue registrando, no subas las apuestas

  CLV
    CLV medio:  +2.94%     Bates el cierre: 73.3%
    CLV t-stat: +13.06   p-valor: 0.0000
    -> bates el cierre de forma consistente: senal solida de ventaja real
```

Las mismas 300 apuestas. El beneficio no puede distinguir la ventaja del azar.
El CLV la confirma sin margen de duda.

**Cómo leer las dos señales juntas:**

| CLV | Resultado a corto | Diagnóstico |
|---|---|---|
| positivo | ganando | vas bien, sigue |
| positivo | perdiendo | **mala suerte** — el método es bueno, no lo cambies |
| negativo | ganando | **suerte** — vas a regresar, no subas las apuestas |
| negativo | perdiendo | el método no funciona, revísalo |

La fila peligrosa es la tercera: es donde la gente sube apuestas justo antes de
devolverlo todo. La segunda es donde la gente abandona un método que sí servía.

---

## Realidades prácticas que el código no arregla

**Te van a limitar la cuenta.** Una casa de apuestas no es un casino: no puede
echarte de la ruleta porque ahí no ganas, pero **sí te limita o cierra la cuenta
en cuanto detecta que ganas**. Tu recompensa por tener ventaja es que te
prohíben usarla. Esto —y no la matemática— es lo que limita el tamaño real de
esta actividad.

**Las cuotas hay que meterlas.** Este módulo lee JSON; conseguir cuotas en vivo
de varias casas requiere una API de datos (de pago) o scraping (contra los
términos de servicio de casi todas). El cuello de botella es la obtención de
datos, no el análisis.

**El nicho importa más que el método.** La cuota de una final de Champions es
casi perfecta: miles de profesionales la han afinado. La de una liga menor no.
La ventaja vive donde la casa dedica menos recursos que tú.

## Reglas de disciplina que el código impone

1. **Nunca apuestes sin EV positivo calculado.** El tracker avisa si registras
   una apuesta con EV negativo según tu propia estimación.
2. **Medio Kelly, no Kelly completo.** Te protege de sobreestimar tu ventaja,
   que es el error garantizado al principio.
3. **Registra la cuota de cierre siempre.** Es la única señal rápida que existe.
4. **Menos de 100 apuestas no significa nada** por resultado. El informe lo dice
   explícitamente en vez de dejarte interpretar un ROI bonito.
5. **No subas las apuestas tras una buena racha** si el CLV no la respalda.
