# FIX_VERDICTS — ветка fix/audit-findings-2026-11-18

Процесс: red→green (коммит «T0 red» с падающими тестами, затем фиксы).
Каждый PoC ревью сначала был **перезапущен против опубликованного кода** —
два PoC не воспроизвелись, это записано честно.

## Верификация PoC ревью (перезапуск до фиксов)

| PoC ревью | Перезапуск | Вердикт |
|---|---|---|
| `print('a'); import torch; print('b')` | ловится старым regex (строки не жадничают на одной кавычке) | ❌ не воспроизвёлся |
| docstring closing line + `import torch` | старый stripper выбрасывал строку целиком → CLEAN | ✅ подтверждён |
| fake `/* */` в Python-строках | `re.S` стирал всё между маркерами → CLEAN | ✅ подтверждён |
| `#` внутри C-строки | Python-правило `#` применялось к C → CLEAN | ✅ подтверждён |
| экранированная кавычка `'don\'t'` | ловится | ❌ не воспроизвёлся |

## Вердикты по задачам

| ID | Что сделано | Тесты | Вердикт |
|---|---|---|---|
| T0 | unittest-каркас, fixtures как .txt, 32 теста | весь набор | ✅ |
| T1 | strip через `tokenize` (Python), state-lexer (C); unparseable → raw scan + WARN | test_poc1..4, test_c_*, test_unparseable_*, test_fstring | ✅ |
| T2 | хук аудирует staged-контент (`git show :f` в mktemp), trap на очистку | test_t2_staged_fraud_blocked, test_t2_clean_staged_passes | ✅ |
| T3 | watcher через `resolve_config`, hot-reload по mtime конфига | TestCliWatcherConfigParity | ✅ |
| T4 | точное самоисключение (2 имени), префикс убран | test_prefix_helpers_not_skipped, test_tools_themselves_skipped | ✅ |
| T6 | `--no-renames -z --diff-filter=ACMR`, NUL-разбор, всё в кавычках | test_t6_filename_with_spaces, test_t6_rename_with_edit | ✅ |
| T7 | fail-closed (нет аудитора/python → exit 1), бэкап+чейнинг прежнего хука, fallback python3→python | test_t7_missing_auditor_blocks, test_t7_existing_hook_chained | ✅ |
| T8 | валидация конфига: severity нормализуется, неизвестное → exit 2, битый regex → exit 2 | TestConfig (3 теста), test_t8_broken_config_blocks_commit | ✅ |
| T9 | единый резолвер: --patterns → repo root → script dir → cwd → built-in | test_resolver_finds_repo_config_from_subdir | ✅ |
| T10 | `.github/workflows/ci.yml`: матрица 3.8/3.11/3.12, тесты + самоаудит дерева + diff examples | CI | ✅ (workflow создан; прогон на GitHub — проверить после push) |
| T11 | зашитый grep расширений убран из хука; аудитор фильтрует сам по конфигу | e2e хука (аудирует .py без grep-фильтра) | ✅ |
| T12 | категория DYNAMIC CODE EXECUTION (warn) в defaults + JSON | test_dynamic_exec_category_exists | ✅ |
| T13 | watcher на argparse; значения опций не теряются; чистка state от удалённых | TestWatcherArgs (4 теста) | ✅ |
| T14 | `dist-info` в suffixes; README: путь `honesty-machine/*`, Windows-заметка | — | ✅ |
| T15 | README limitations обновлены (оставлено только истинное); 2 новых примера обходов; этот файл | test_examples_output_matches | ✅ |

## Записанные изменения счётчиков (по ТЗ — с обоснованием)

- `fraud_hidden_in_c_string.c`: x3 → **x4**. Причина: новый C-lexer сохраняет
  `/* gradient descent step */` ВНУТРИ строкового литерала (там живут ядра GPU),
  старый stripper вырезал его глобально. Повышение чувствительности, не ослабление.
- `examples/expected_output.txt` перегенерирован: добавлены 2 новых примера обходов.

## Сознательно НЕ сделано (не замолчано)

- C++ raw strings `R"(...)"` — documented limitation в README и коде.
- F-strings на Python 3.8–3.11: выражения внутри не сканируются (нет FSTRING_*
  токенов) — documented limitation; на 3.12+ сканируются (тест есть).

## Серверный гейт — проверен боем (2026-11-18)

- CI-матрица 3.8 / 3.11 / 3.12 на PR: **зелёная** (run 44309775966).
- Ловушка: коммит с `import torch` (ci_trap.py). Локальный гейт **заблокировал**
  коммит; обход через `--no-verify` (документированный); CI на GitHub **покраснел**
  на обоих событиях (push + PR). Ловушка удалена коммитом b4244ca.
- Вывод: локальный хук обходим (как и заявлено в README), серверный гейт — нет.
  Именно поэтому настоящие ворота — CI.

## Что требует ревизора

По METHODOLOGY.md завершением считается перезапуск **другой моделью с чистого
клона**: `python -m unittest discover -s tests` + `python honest_audit.py .` +
`python honest_audit.py examples/` и diff с `expected_output.txt`.
