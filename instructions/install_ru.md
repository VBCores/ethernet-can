# Установка клиента на Linux

[English](install.md)

[Выбор подключения](../README_ru.md)

Пакеты предназначены для Ubuntu 22.04/24.04, amd64 и arm64. Интернет нужен для загрузки пакета и зависимостей APT. Проверенный на текущем стенде вариант будет указан в release notes.

## Установка пакета

Для последнего стабильного релиза:

```bash
wget -qO- https://github.com/VBCores/ethernet-can/releases/latest/download/install.sh | bash
```

Скрипт всегда устанавливает последний стабильный пакет, даже если скачан из
старого релиза. Для установки конкретной версии скачайте её `.deb` напрямую
со страницы релиза и выполните `sudo apt install ./имя-пакета.deb`.
Скрипт выбирает архитектуру,
проверяет SHA-256, выполняет `apt update` и `apt install -y`, удаляет временные
файлы даже при ошибке. Нужны Bash, wget, стандартные утилиты Ubuntu и sudo
(либо запуск от root). RC не попадают в `latest`; старые RC могут не содержать скрипт.

Команда выполняет скачанный код. Если хотите сначала проверить его:

```bash
wget -O install.sh https://github.com/VBCores/ethernet-can/releases/latest/download/install.sh
less install.sh
bash install.sh
```

В автоматизации используйте `set -o pipefail` перед командой с pipe, чтобы
ошибка скачивания скрипта тоже дала ненулевой код завершения. На VM с устаревшим
APT-источником `file:///cdrom` сначала отключите этот недоступный источник;
установщик настройки репозиториев APT не меняет.

Служба установлена, но при первой установке не запускается. Создайте рабочую конфигурацию по выбранной инструкции, затем включите службу. Для работы с примерами без Git скопируйте установленные документы в свой каталог:

```bash
setup_dir=$(mktemp -d "$HOME/ethernet-can-setup.XXXXXX")
cp -R /opt/voltbro/ethernet-can/docs/. "$setup_dir/"
cd "$setup_dir"
```

Все команды инструкций с путями `instructions/...` выполняйте из этого каталога (или из корня репозитория при сборке из исходников).

## Обновление и удаление

Для обновления повторите загрузку и `apt install`. Работающая служба перезапустится; остановленная останется остановленной. Пользовательские JSON сохраняются. Обычный `apt upgrade` не ищет релизы на GitHub.

`sudo apt remove ethernet-can-host` останавливает службу и удаляет пакет; пользовательские JSON остаются. Сетевые настройки и системный DNS пакет не перенастраивает.

Экспериментальный пакет `0.1.0` содержал старые скрипты, отключающие службу при обновлении. При переходе с него заранее запишите состояние службы и после установки восстановите его вручную. Это ограничение старого пакета.

## Сборка из исходников

```bash
sudo apt update
sudo apt install -y git build-essential cmake dpkg-dev python3 python3-requests python3-tenacity iproute2 kmod can-utils
git clone --recurse-submodules https://github.com/VBCores/ethernet-can
cd ethernet-can
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j2
(cd build && cpack -G DEB)
sudo apt install ./build/ethernet-can-host_$(dpkg --print-architecture).deb
```
