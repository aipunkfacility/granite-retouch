# Правила написания промптов — Granite Retouch

## Основной принцип

Пиши промпт как инструкцию художнику, а не как техническую спецификацию. Естественный язык, полные предложения, связный рассказ. Модель лучше понимает описание в свободной форме, чем нумерованные списки и таблицы параметров.

## Структура

- Один связный текст, ~25–35 строк
- Без нумерованных секций и списков параметров
- Без отдельных блоков «Quality Requirements» / «Reference Targets» — всё сказано один раз, на своём месте
- Ограничения яркости указываются один раз, не повторяются в пяти местах

## Язык

- Промпты только на английском
- Прямые, конкретные инструкции: «the upper face reads as the illuminated side»
- Без хеджирования: никакого «subtle», «micro», «gentle», «uniform at first glance» — это говорит модели «не утруждайся»
- Без языка реставрации: «preserve and enhance», «repair blur», «restore» — модель генерирует с нуля, используй язык генерации: «render matching the source photo exactly»

## Чего НЕ писать

### Не повторяй очевидное из исходника
- **Поза/ракурс**: Если поза не меняется, пиши «Keep the original pose and angle exactly as in the source» — НЕ повторяй «3/4 view, slightly turned to the right». Модель видит фото; пересказ того, что она уже видит, размывает сигнал.
- **Композиция**: Если композиция не меняется, НЕ пиши «Render the subject from the shoulders up» или «Frame the subject from the shoulders up» — это указание модели изменить крупность. Просто не упоминай композицию.
- **Типы головных уборов**: Не перечисляй «(cap, peaked cap, beret, etc.)» — модель видит головной убор на фото.
- **Детали одежды, которых нет**: Не пиши «buttons, stitching», если нет пуговиц. Описывай только то, что реально есть.

### Не добавляй блики/яркость на кожу
- «brightest highlights on forehead, cheekbones, nose bridge» → модель рисует яркие пятна на лице
- «specular highlights», «silver luminosity» → та же проблема: горячие точки вместо плавной тональной вариации
- Вместо этого описывай направление: «the upper face reads as the illuminated side, the lower sides fall into shadow» — пусть модель сама выводит тональные значения из описания освещения

### Не пихай числа яркости в описание кожи
- ❌ «highlights 190–215, shadows 130–170» — читается как техническая спецификация, а не инструкция
- ✅ Описывай зоны света и тени естественно, ограничения яркости дай один раз отдельной строкой (потолок, белки глаз)

### Не хеджируй тональную вариацию
- ❌ «subtle tonal micro-variation», «gentle tonal breathing», «uniform at first glance»
- ✅ «visible tonal range», «clearly distinct light and shadow regions», «the transitions between light and shadow must be visible and natural»

### Не пиши «or» в body_details — будь точным
- ❌ «metal badge or crest pin»
- ✅ «metal cockade pin» — оператор подтвердил, что это кокарда, пиши точно и один раз

### Не перечисляй то, чего нет
- ❌ «folds, buttons, stitching» когда пуговиц нет
- ✅ «visible fabric texture and detail» — достаточно общо, не придумывает несуществующие детали
- ❌ «Render all medals, orders, and insignia exactly as visible in the source photo» — если медалей нет, модель нарисует их из ничего
- ✅ «Render all visible uniform details and insignia matching the source photo exactly» — без перечисления, модель отрисует только то, что реально есть

## Принцип Anti-Doll

Вшивается естественно в конец промпта, не отдельной секцией:
- «The portrait must look like a photograph, not an illustration — smooth, gradual transitions, no harsh black stripes on skin. Work with light, not with lines.»
- Этого достаточно. Не нужен 5-строчный CRITICAL-блок, повторяющий «smooth transitions», уже сказанные в других местах.

## Body Details

**Факт наличия = обязательно. Внешний вид = запрещено.**

- Вставка между garment-описанием и headgear
- Указывай только факт наличия и локацию: «earring on the left earlobe», а не «small dark-toned stud earring». Если элемент не упомянуть — модель может его не сгенерировать. Если описать внешний вид — модель генерит по описанию вместо референса.
- Формат: «[location] — [type of detail]»
- Без описания внешнего вида — модель видит, как выглядит серьга/тату/шрам
- В constraints: «Anything visible on the body/face that is not clothing must be reproduced in the generated image.» — без языка редактирования («do not remove or blur»), модель генерирует с нуля

## Описание одежды

**Факт наличия = обязательно. Внешний вид = запрещено.**

Модель видит фото и знает, как выглядит каждый элемент. Но модель НЕ знает, какие элементы критичны — если элемент не упомянут, модель может его не сгенерировать (пропущенная пуговица → пуговицы нет на генерации). Если описать внешний вид неточно — модель сгенерит по описанию вместо референса.

Указывай: **тональную перекодировку** + **перечень видимых элементов** (без описания внешнего вида).

- ❌ «The coat is charcoal gray with stand collar, button at center front, V-shaped neckline, and fold shadows» — описание внешнего вида. VLM ошибся (нет стойки, нет V-выреза), модель сгенерит по описанию вместо фото.
- ❌ «Render the clothing matching the source photo exactly» — слишком общо, модель может пропустить конкретные элементы
- ✅ «Render the clothing matching the source photo exactly. Map tonal ranges: the coat as charcoal gray, the shirt as light gray. Note visible elements: button at center front of the coat.» — тональная перекодировка + факт наличия элементов без описания внешнего вида

Если VLM указал неточные детали (напр. «stand collar» когда стойки нет), не включай их — модель видит реальный крой на фото.
Если одежда меняется (civilian) — тогда описывай конкретно, потому что референса нет.

## Ограничения яркости

Каждое указывается один раз:
- Ни один участок кожи не превышает brightness 245
- Только белки глаз могут достигать 250–255
- Ничто на лице не ярче белков глаз
- Одежда темнее лица
- Тени на тёмной одежде выше 0

Без отдельного блока «Reference Targets» или «Goal», повторяющего эти числа.

## Описание освещения

- Назови паттерн (напр., «frontal butterfly»)
- Опиши какие зоны освещены, какие в тени
- Позволь модели самой вывести тональные значения из направления света — не прописывай brightness-числа по зонам
- Rim light: описывай как естественный эффект контровика, а не как значения яркости

## Чеклист перед отправкой

- [ ] Поза/ракурс не повторяются, если не меняются
- [ ] Нет бликов/specular на коже
- [ ] Нет чисел яркости в описании кожи (потолок и белки — ок)
- [ ] Нет хеджирующих слов (subtle, micro, gentle, uniform)
- [ ] Нет языка реставрации (preserve, restore, enhance, repair)
- [ ] Нет перечислений того, чего нет на фото (пуговицы, типы головных уборов, медали/ордена)
- [ ] Композиция не указана, если не меняется
- [ ] Одежда не переописана — только тональная перекодировка + «matching the source»
- [ ] Body details не переописаны — только факт наличия, без внешнего вида
- [ ] Нет аналогий-объяснений («too bright and you get alien eyes») — только директивы
- [ ] Нет «or» в body_details — только точные описания
- [ ] Нет отдельных блоков Quality Requirements / Reference Targets
- [ ] Ограничения яркости указаны один раз, не повторяются
- [ ] Промпт читается как естественный английский, ~25–35 строк
- [ ] Anti-Doll — закрывающая фраза, не секция
