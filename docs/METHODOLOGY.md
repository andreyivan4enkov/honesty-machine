# Methodology / Методология

[EN below | RU ниже]

---

## EN — The process that catches what the linter cannot

The auditor is a gate, not a proof. Regex catches *words*; fraud lives in *meaning*.
The complete defense is a process with mechanical enforcement at every step.

### The pipeline (every claim, every time)

```
CLAIM  →  CODE  →  MEASUREMENT  →  INDEPENDENT RERUN  →  VERDICT
verbatim   saved      numbers        a different agent       recorded in
with ID    script     + baselines    reruns the script     the table
```

1. **Claim, verbatim.** Quote the thesis exactly, give it an ID. Ambiguous claims
   cannot be refuted — that is what makes them dangerous.
2. **Saved, runnable code.** A measurement made in a one-off inline script is a
   process violation even if the number is correct: nobody can rerun it. The script
   must live in the repo and run with one command.
3. **Measurement with baselines.** Every result ships next to:
   - the baseline it claims to beat (same data, same metric),
   - the random level.
   A number without a baseline in the same report is marketing.
4. **Independent rerun.** The reviewer does not read your report — the reviewer
   *runs your script*. In multi-agent setups: one model builds, another model
   reruns. This is the step that caught "92% > 86%" (parity on fresh data) and
   "92%/97%" (numbers that the current file could not produce at all).
5. **Verdict, recorded.** ✅ confirmed / ⚠️ partial / ❌ refuted / not tested.
   Append to the results table; never overwrite a working version of a file —
   version them (`*_v2.py`).

### Determinism rule

If the design claims determinism: run twice, diff the outputs, write down
"MATCHED". Randomness in the forward pass is fraud; seeds in the *test harness*
are legitimate.

### Metric discipline

Never switch the metric mid-report. If accuracy looks bad and you switch to
perplexity halfway, that is a red flag, not a result.

### Cross-model review (proven pattern)

- Builder agent: implements and measures.
- Reviewer agent (different model/family): receives only the script paths and the
  claims — not the builder's narrative. Reruns everything. Marks what was NOT
  rerun as "not rerun".
- Escalation: any claim the reviewer cannot reproduce goes to quarantine with a
  manifest entry (path → reason → date), not to the trash — history matters.

### Why WARN severity exists

`argmax` is fraud in a selector mechanism and completely legal in a measurement
harness. `tanh` is a rejected formula in one place and legal mathematics
(Poincaré ball) in another. The auditor flags; the human judges context.
Blocking everything would teach people to disable the gate.

---

## RU — Процесс, который ловит то, что линтер не может

Аудитор — ворота, а не доказательство. Regex ловит *слова*; подлог живёт в *смысле*.
Полная защита — процесс с механическим принуждением на каждом шаге.

### Конвейер (каждый тезис, каждый раз)

```
ТЕЗИС  →  КОД  →  ЗАМЕР  →  НЕЗАВИСИМЫЙ ПЕРЕЗАПУСК  →  ВЕРДИКТ
дословно  сохранённый  цифры +    другой агент            записан в
с ID      скрипт       базлайны   перезапускает          таблицу
```

1. **Тезис дословно.** Цитата + ID. Размытый тезис нельзя опровергнуть — этим он
   и опасен.
2. **Сохранённый запускаемый код.** Замер одноразовым инлайн-скриптом — нарушение
   процесса, даже если цифра верна: перезапустить нельзя. Скрипт живёт в репо и
   запускается одной командой.
3. **Замер с базлайнами.** Каждый результат — рядом с базлайном (те же данные, та
   же метрика) и со случайным уровнем. Цифра без базлайна в том же отчёте — маркетинг.
4. **Независимый перезапуск.** Ревизор не читает отчёт — ревизор *запускает скрипт*.
   В мульти-агентной схеме: одна модель строит, другая перезапускает. Именно этот шаг
   поймал «92% > 86%» (паритет на свежих данных) и «92%/97%» (цифры, которые текущий
   файл вообще не мог выдать).
5. **Вердикт — записан.** ✅ / ⚠️ / ❌ / не проверено. Дописывать в таблицу; рабочую
   версию файла не перезаписывать — версионировать (`*_v2.py`).

### Правило детерминизма

Если дизайн заявляет детерминизм: прогнать дважды, сравнить вывод, записать
«СОВПАЛО». Случайность в форварде — подлог; сиды в *тестовой обвязке* — законны.

### Дисциплина метрики

Метрику посреди отчёта не переключают. Точность разочаровала и вы перешли на
перплексию — это красный флаг, а не результат.

### Кросс-модельная ревизия (проверенный паттерн)

- Агент-строитель: реализует и меряет.
- Агент-ревизор (другая модель/семейство): получает только пути скриптов и тезисы —
  без нарратива строителя. Перезапускает всё. Что не перезапускал — помечает.
- Эскалация: невоспроизводимое уходит в карантин с записью в манифесте
  (путь → причина → дата), не в корзину — история важна.

### Зачем существует уровень WARN

`argmax` — подлог в механизме селектора и совершенно законен в измерительной
обвязке. `tanh` — отвергнутая формула в одном месте и законная математика (сфера
Пуанкаре) в другом. Аудитор флагает; контекст судит человек. Блокировать всё —
научить людей отключать ворота.
