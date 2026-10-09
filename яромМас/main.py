from flask import Flask, render_template, request, jsonify
import numpy as np
import pandas as pd
import time
import threading
import random

# Инициализация Flask-приложения
app = Flask(__name__)

# --- НАСТРОЙКИ И ГЛОБАЛЬНОЕ СОСТОЯНИЕ ---
ROWS = 20  # Количество строк в матрице
COLS = 30  # Количество столбцов в матрице

# Глобальная матрица (состояние симуляции). 
# Инициализируется нулями. Тип int для экономии памяти.
matrix_global = np.zeros((ROWS, COLS), dtype=int)

# Замок (Lock) для обеспечения потокобезопасности.
# Необходим, так как к matrix_global одновременно обращаются:
# 1) Фоновый поток (читает и изменяет)
# 2) Flask-маршруты (читают и изменяют по запросу пользователя)
lock = threading.Lock()


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_neighbors(i, j):
    """
    Возвращает список координат соседних клеток (верх, низ, лево, право).
    Проверяет границы матрицы, чтобы не выйти за пределы индексов.
    """
    neighbors = []
    if i > 0:
        neighbors.append((i - 1, j))      # Сосед сверху
    if i < ROWS - 1:
        neighbors.append((i + 1, j))      # Сосед снизу
    if j > 0:
        neighbors.append((i, j - 1))      # Сосед слева
    if j < COLS - 1:
        neighbors.append((i, j + 1))      # Сосед справа
    return neighbors


# --- ФОНОВЫЙ ПОТОК (ДВИЖОК СИМУЛЯЦИИ) ---
def decrement_worker():
    """
    Бесконечный цикл, который обновляет состояние матрицы каждую секунду.
    """
    while True:
        time.sleep(1)  # Пауза в 1 секунду между "тиками" симуляции

        # Захватываем замок, чтобы во время обновления веб-пользователь 
        # не прочитал/не изменил матрицу наполовину
        with lock:
            for i in range(ROWS):
                for j in range(COLS):
                    if matrix_global[i, j] > 0:
                        # 1) "Затухание": уменьшаем значение клетки на 1
                        matrix_global[i, j] -= 1

                        # 2) "Распространение": с шансом 75% 
                        if random.random() < 0.75:
                            neighbors = get_neighbors(i, j)
                            if neighbors:
                                # Выбираем случайного соседа и добавляем ему +2
                                ni, nj = random.choice(neighbors)
                                matrix_global[ni, nj] += 2


# Запускаем фоновый поток при старте приложения.
# daemon=True означает, что поток автоматически "умрет" при закрытии главного процесса Flask.
threading.Thread(target=decrement_worker, daemon=True).start()


# --- МАРШРУТЫ (ROUTES) ---

@app.route('/', methods=['GET', 'POST'])
def rfr():
    """
    Главная страница. Отображает матрицу и позволяет пользователю 
    вручную вводить значения через HTML-форму.
    """
    # Если форма была отправлена (метод POST)
    if request.method == 'POST':
        with lock:  # Блокируем матрицу на время записи
            for i in range(ROWS):
                for j in range(COLS):
                    # Получаем значение из формы по имени поля 'cell_i_j'
                    value = request.form.get(f'cell_{i}_{j}', 0)
                    try:
                        matrix_global[i, j] = int(value)
                    except ValueError:
                        # Если пользователь ввел не число, оставляем 0
                        matrix_global[i, j] = 0

    # ПРИМЕЧАНИЕ: Эта строка создает DataFrame, но он нигде не используется.
    # Это лишняя трата памяти и процессорного времени.
    df = pd.DataFrame(matrix_global)

    with lock:  # Блокируем матрицу на время чтения
        # Конвертируем numpy-массив в обычный вложенный список Python,
        # чтобы Jinja2 (шаблонизатор) мог легко его отобразить в HTML
        matrix_list = matrix_global.tolist()

    # Отправляем данные в HTML-шаблон
    return render_template('matrix.html',
                           matrix_list=matrix_list,
                           rows=ROWS,
                           cols=COLS)


@app.route('/api/matrix')
def api_matrix():
    """
    API-эндпоинт. Отдает текущее состояние матрицы в формате JSON.
    Удобно для получения данных через JavaScript (AJAX/Fetch) без перезагрузки страницы.
    """
    with lock:
        data = matrix_global.tolist()
    # jsonify автоматически устанавливает правильный Content-Type (application/json)
    return jsonify(data)


# --- ТОЧКА ВХОДА ---
if __name__ == '__main__':
    # use_reloader=False ОБЯЗАТЕЛЬНО в данном случае!
    # Если включить reloader (стандартно для debug=True), Flask запустит 
    # процесс дважды, и у вас будет ДВА фоновых потока, которые будут 
    # хаотично ломать одну и ту же матрицу.
    app.run(debug=True, use_reloader=False)
