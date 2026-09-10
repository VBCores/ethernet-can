# Установка клиента на Linux

[English](install.md)

[Выбор подключения](../README_ru.md)

Пакеты предназначены для Ubuntu 22.04/24.04, amd64 и arm64. Интернет нужен для загрузки пакета и зависимостей APT. Проверенный на текущем стенде вариант будет указан в release notes.

## Установка пакета

Для стабильного релиза:

```bash
arch=$(dpkg --print-architecture)
case "$arch" in amd64|arm64) ;; *) echo "Unsupported architecture: $arch"; exit 1 ;; esac
wget -O ethernet-can-host.deb \
  "https://github.com/VBCores/ethernet-can/releases/latest/download/ethernet-can-host_${arch}.deb" &&
sudo apt update &&
sudo apt install ./ethernet-can-host.deb &&
rm ethernet-can-host.deb
```

Для RC замените `latest/download` на `download/v0.3.0-rc.2` и используйте тег существующего prerelease. RC не попадают в `latest`. Ссылки работают после публикации соответствующего релиза.

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
