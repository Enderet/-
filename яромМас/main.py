from flask import Flask, render_template, request, jsonify
import numpy as np
import pandas as pd
import time
import threading
import random

app = Flask(__name__)

# Размеры матрицы
ROWS = 20
COLS = 30

# Глобальная матрица
matrix_global = np.zeros((ROWS, COLS), dtype=int)

# Замок для потокобезопасности (фоновый поток + Flask-маршруты
# обращаются к одной и той же матрице)
lock = threading.Lock()


def get_neighbors(i, j):
    """Возвращает список координат соседних клеток (верх, низ, лево, право)."""
    neighbors = []
    if i > 0:
        neighbors.append((i - 1, j))      # верх
    if i < ROWS - 1:
        neighbors.append((i + 1, j))      # низ
    if j > 0:
        neighbors.append((i, j - 1))      # лево
    if j < COLS - 1:
        neighbors.append((i, j + 1))      # право
    return neighbors


# --- Фоновый поток ---
def decrement_worker():
    while True:
        time.sleep(1)

        with lock:
            for i in range(ROWS):
                for j in range(COLS):
                    if matrix_global[i, j] > 0:
                        # 1) Уменьшаем клетку на 1
                        matrix_global[i, j] -= 1

                        # 2) С шансом 50% случайный сосед получает +2
                        if random.random() < 0.5:
                            neighbors = get_neighbors(i, j)
                            if neighbors:
                                ni, nj = random.choice(neighbors)
                                matrix_global[ni, nj] += 2


# Запускаем поток один раз при старте
threading.Thread(target=decrement_worker, daemon=True).start()


# --- Главная страница ---
@app.route('/', methods=['GET', 'POST'])
def rfr():
    if request.method == 'POST':
        with lock:
            for i in range(ROWS):
                for j in range(COLS):
                    value = request.form.get(f'cell_{i}_{j}', 0)
                    try:
                        matrix_global[i, j] = int(value)
                    except ValueError:
                        matrix_global[i, j] = 0

    df = pd.DataFrame(matrix_global)

    with lock:
        matrix_list = matrix_global.tolist()

    return render_template('matrix.html',
                           matrix_list=matrix_list,
                           rows=ROWS,
                           cols=COLS)


# --- API: отдаёт текущее состояние матрицы ---
@app.route('/api/matrix')
def api_matrix():
    with lock:
        data = matrix_global.tolist()
    return jsonify(data)


if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)