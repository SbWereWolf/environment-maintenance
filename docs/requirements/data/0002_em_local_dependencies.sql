-- depends: 0001_em_port_agreement
INSERT INTO requirements(id, level, status, text) VALUES ('EM-SYS-INDEPENDENT-APPLICATION-DEPENDENCIES', 'system', 'future', 'Приложения используют собственные управляемые зависимости с заданной версией и сохраняют независимость при их восстановлении.');
INSERT INTO requirements(id, level, status, text) VALUES ('EM-APP-LOCAL-TOOLING-DEPENDENCY', 'application', 'future', 'Каждое приложение использует собственный установленный экземпляр инструментальной зависимости и её отдельное окружение выполнения.');
INSERT INTO requirements(id, level, status, text) VALUES ('EM-APP-REPRODUCIBLE-DEPENDENCY', 'application', 'future', 'Зафиксированные метаданные и входные материалы позволяют восстановить выбранную версию зависимости с подтверждением целостности.');
INSERT INTO requirements(id, level, status, text) VALUES ('EM-APP-INDEPENDENT-DEPENDENCY-RECOVERY', 'application', 'future', 'Восстановление зависимости одного приложения сохраняет установленные зависимости и работоспособность других приложений.');
INSERT INTO requirements(id, level, status, text) VALUES ('EM-APP-OWNED-DEPENDENCY-INVOCATION', 'application', 'future', 'Вызовы инструментов приложения используют принадлежащую ему установленную зависимость, сохраняя данные и посторонние настройки.');
INSERT INTO requirement_links(system_id, application_id) VALUES ('EM-SYS-INDEPENDENT-APPLICATION-DEPENDENCIES', 'EM-APP-LOCAL-TOOLING-DEPENDENCY');
INSERT INTO requirement_links(system_id, application_id) VALUES ('EM-SYS-INDEPENDENT-APPLICATION-DEPENDENCIES', 'EM-APP-REPRODUCIBLE-DEPENDENCY');
INSERT INTO requirement_links(system_id, application_id) VALUES ('EM-SYS-INDEPENDENT-APPLICATION-DEPENDENCIES', 'EM-APP-INDEPENDENT-DEPENDENCY-RECOVERY');
INSERT INTO requirement_links(system_id, application_id) VALUES ('EM-SYS-INDEPENDENT-APPLICATION-DEPENDENCIES', 'EM-APP-OWNED-DEPENDENCY-INVOCATION');
UPDATE requirements_meta SET revision=2 WHERE revision=1;
