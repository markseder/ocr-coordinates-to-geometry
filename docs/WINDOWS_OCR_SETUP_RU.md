# Установка RapidOCR для QGIS 4 в Windows 10/11

Сам плагин устанавливается обычным ZIP-файлом. Для кнопки «Распознать» один
раз нужно добавить RapidOCR в Python, поставляемый вместе с QGIS.

## Вариант 1 — OSGeo4W Shell

1. Закройте QGIS.
2. В меню «Пуск» откройте **OSGeo4W Shell**.
3. Выполните:

   ```bat
   python-qgis.bat -m pip install --upgrade rapidocr onnxruntime
   ```

4. Запустите QGIS заново и откройте плагин.

## Проверка

В OSGeo4W Shell выполните:

```bat
python-qgis.bat -c "from rapidocr import RapidOCR; print('RapidOCR OK')"
```

Если появилась строка `RapidOCR OK`, зависимость установлена правильно.

## Если команда python-qgis.bat не найдена

Откройте папку установки QGIS и найдите `python-qgis.bat`. Обычно он находится
в папке `bin`. Запустите команду, указав полный путь в кавычках, например:

```bat
"C:\Program Files\QGIS 4.0.0\bin\python-qgis.bat" -m pip install --upgrade rapidocr onnxruntime
```

Фактическая папка зависит от сборки QGIS. Не устанавливайте RapidOCR в обычный
Python с python.org: плагин его не увидит.

## Конфиденциальность

Распознавание выполняется локально. Скриншоты и координаты никуда не
отправляются.
