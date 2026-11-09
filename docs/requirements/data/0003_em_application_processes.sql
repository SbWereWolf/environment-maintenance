-- depends: 0002_em_local_dependencies
INSERT INTO requirements(id, level, status, text) VALUES ('EM-SYS-APPLICATION-OPERATIONS', 'system', 'future', 'Оператор обслуживает и запускает выбранные приложения системы, просматривает и завершает их зарегистрированные запуски по окружениям с сохранением состояния остальных приложений.');
INSERT INTO requirements(id, level, status, text) VALUES ('EM-APP-DECLARED-OPERATIONS', 'application', 'future', 'При обслуживании оператор выбирает объявленные ресурсы, получает проверку идентификаторов и понятный результат вызова с сохранением согласованного состава обслуживания.');
INSERT INTO requirements(id, level, status, text) VALUES ('EM-APP-ENVIRONMENT-LAUNCHES', 'application', 'future', 'При запуске выбранных приложений в окружении оператор получает сохранённый учёт их запусков, результаты отдельных попыток и возможность просмотреть ещё не запущенные приложения.');
INSERT INTO requirements(id, level, status, text) VALUES ('EM-APP-REGISTERED-LAUNCH-STOP', 'application', 'future', 'Оператор просматривает зарегистрированные окружения и завершает выбранные запуски по сохранённому учёту, получая результаты каждой цели с сохранением остальных записей.');
INSERT INTO requirements(id, level, status, text) VALUES ('EM-APP-OPERATION-GUIDANCE', 'application', 'future', 'Оператор получает актуальные инструкции обслуживания, запуска, остановки и перехода между версиями для инструмента и использующих его приложений.');
INSERT INTO requirement_links(system_id, application_id) VALUES ('EM-SYS-APPLICATION-OPERATIONS', 'EM-APP-DECLARED-OPERATIONS');
INSERT INTO requirement_links(system_id, application_id) VALUES ('EM-SYS-APPLICATION-OPERATIONS', 'EM-APP-ENVIRONMENT-LAUNCHES');
INSERT INTO requirement_links(system_id, application_id) VALUES ('EM-SYS-APPLICATION-OPERATIONS', 'EM-APP-REGISTERED-LAUNCH-STOP');
INSERT INTO requirement_links(system_id, application_id) VALUES ('EM-SYS-APPLICATION-OPERATIONS', 'EM-APP-OPERATION-GUIDANCE');
UPDATE requirements_meta SET revision=3 WHERE revision=2;
