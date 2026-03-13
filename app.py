from flask import Flask, render_template, request, redirect
import sqlite3
from datetime import date

app = Flask(__name__)

# =========================
# CONEXIÓN DB
# =========================

def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

# =========================
# FORMATO MONETARIO
# =========================

def fmt(n):
    return f"{int(n):,}".replace(",", ".")

@app.context_processor
def inject_fmt():
    return dict(fmt=fmt)

# =========================
# INICIALIZACIÓN DB
# =========================

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS categoria (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS producto (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        precio_venta INTEGER,
        stock INTEGER,
        categoria_id INTEGER
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS proveedor (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        telefono TEXT,
        email TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS compra (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        proveedor_id INTEGER,
        fecha DATE,
        total INTEGER,
        estado TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS detalle_compra (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        compra_id INTEGER,
        producto_id INTEGER,
        cantidad INTEGER,
        precio_compra INTEGER,
        fecha DATE
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS venta (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha DATE,
        total INTEGER,
        estado TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS detalle_venta (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        venta_id INTEGER,
        producto_id INTEGER,
        cantidad INTEGER,
        precio_venta INTEGER,
        fecha DATE
    );
    """)

    conn.commit()
    conn.close()

init_db()

# =========================
# RUTAS OBLIGATORIAS
# =========================

@app.route("/")
def inicio():
    return redirect("/dashboard")

# =========================
# DASHBOARD
# =========================

@app.route("/dashboard")
def dashboard():
    conn = get_db()
    cur = conn.cursor()

    total_ventas = cur.execute("SELECT SUM(total) FROM venta WHERE estado='confirmada'").fetchone()[0] or 0
    total_compras = cur.execute("SELECT SUM(total) FROM compra WHERE estado='confirmada'").fetchone()[0] or 0
    total_productos = cur.execute("SELECT COUNT(*) FROM producto").fetchone()[0] or 0
    inventario = cur.execute("SELECT SUM(precio_venta * stock) FROM producto").fetchone()[0] or 0

    mas_vendido = cur.execute("""
        SELECT producto.nombre, SUM(detalle_venta.cantidad) as total
        FROM detalle_venta
        JOIN producto ON producto.id = detalle_venta.producto_id
        GROUP BY producto.id
        ORDER BY total DESC
        LIMIT 1
    """).fetchone()

    mas_comprado = cur.execute("""
        SELECT producto.nombre, SUM(detalle_compra.cantidad) as total
        FROM detalle_compra
        JOIN producto ON producto.id = detalle_compra.producto_id
        GROUP BY producto.id
        ORDER BY total DESC
        LIMIT 1
    """).fetchone()

    ultima_venta = cur.execute("SELECT * FROM venta WHERE estado='confirmada' ORDER BY id DESC LIMIT 1").fetchone()
    ultima_compra = cur.execute("SELECT * FROM compra WHERE estado='confirmada' ORDER BY id DESC LIMIT 1").fetchone()

    borradores = cur.execute("SELECT COUNT(*) FROM venta WHERE estado='borrador'").fetchone()[0] + \
                 cur.execute("SELECT COUNT(*) FROM compra WHERE estado='borrador'").fetchone()[0]

    conn.close()

    return render_template("dashboard.html",
        total_ventas=total_ventas,
        total_compras=total_compras,
        total_productos=total_productos,
        inventario=inventario,
        mas_vendido=mas_vendido,
        mas_comprado=mas_comprado,
        ultima_venta=ultima_venta,
        ultima_compra=ultima_compra,
        borradores=borradores
    )

# =========================
# CATEGORÍAS
# =========================

@app.route("/categorias", methods=["GET", "POST"])
def categorias():
    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        nombre = request.form["nombre"].strip().lower()
        if nombre != "":
            cur.execute("INSERT INTO categoria (nombre) VALUES (?)", (nombre,))
            conn.commit()
        return redirect("/categorias")

    categorias = cur.execute("SELECT * FROM categoria").fetchall()
    conn.close()
    return render_template("categorias.html", categorias=categorias)

# =========================
# PRODUCTOS
# =========================

@app.route("/productos", methods=["GET", "POST"])
def productos():
    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        nombre = request.form["nombre"].strip().lower()
        precio_venta = request.form["precio_venta"].strip().lower()
        categoria_id = request.form["categoria_id"].strip().lower()

        if not precio_venta.isdigit():
            return redirect("/productos")

        precio_venta = int(precio_venta)

        if precio_venta <= 0:
            return redirect("/productos")

        cur.execute("""
            INSERT INTO producto (nombre, precio_venta, stock, categoria_id)
            VALUES (?, ?, 0, ?)
        """, (nombre, precio_venta, categoria_id))

        conn.commit()
        return redirect("/productos")

    productos = cur.execute("""
        SELECT producto.*, categoria.nombre as categoria
        FROM producto
        LEFT JOIN categoria ON categoria.id = producto.categoria_id
    """).fetchall()

    categorias = cur.execute("SELECT * FROM categoria").fetchall()
    conn.close()
    return render_template("productos.html", productos=productos, categorias=categorias)

# =========================
# PROVEEDORES
# =========================

@app.route("/proveedores", methods=["GET", "POST"])
def proveedores():
    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        nombre = request.form["nombre"].strip().lower()
        telefono = request.form["telefono"].strip().lower()
        email = request.form["email"].strip().lower()

        cur.execute("""
            INSERT INTO proveedor (nombre, telefono, email)
            VALUES (?, ?, ?)
        """, (nombre, telefono, email))

        conn.commit()
        return redirect("/proveedores")

    proveedores = cur.execute("SELECT * FROM proveedor").fetchall()
    conn.close()
    return render_template("proveedores.html", proveedores=proveedores)

# =========================
# COMPRAS
# =========================

@app.route("/compras", methods=["GET", "POST"])
def compras():
    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST" and request.form.get("crear_documento"):
        proveedor_id = request.form["proveedor_id"].strip().lower()
        if proveedor_id == "":
            return redirect("/compras")

        cur.execute("""
            INSERT INTO compra (proveedor_id, fecha, total, estado)
            VALUES (?, ?, 0, 'borrador')
        """, (proveedor_id, date.today()))
        conn.commit()
        return redirect("/compras")

    if request.method == "POST" and request.form.get("agregar_detalle"):
        compra_id = request.form["compra_id"].strip().lower()
        producto_id = request.form["producto_id"].strip().lower()
        cantidad = request.form["cantidad"].strip().lower()
        precio_compra = request.form["precio_compra"].strip().lower()

        if not cantidad.isdigit():
            return redirect("/compras")

        cantidad = int(cantidad)
        if cantidad <= 0:
            return redirect("/compras")

        if not precio_compra.isdigit():
            return redirect("/compras")

        precio_compra = int(precio_compra)
        if precio_compra <= 0:
            return redirect("/compras")

        estado = cur.execute("SELECT estado FROM compra WHERE id=?", (compra_id,)).fetchone()
        if not estado or estado["estado"] != "borrador":
            return redirect("/compras")

        cur.execute("""
            INSERT INTO detalle_compra (compra_id, producto_id, cantidad, precio_compra, fecha)
            VALUES (?, ?, ?, ?, ?)
        """, (compra_id, producto_id, cantidad, precio_compra, date.today()))

        conn.commit()
        return redirect("/compras")

    compras = cur.execute("""
        SELECT compra.*, proveedor.nombre as proveedor
        FROM compra
        JOIN proveedor ON proveedor.id = compra.proveedor_id
        ORDER BY compra.id DESC
    """).fetchall()

    proveedores = cur.execute("SELECT * FROM proveedor").fetchall()
    productos = cur.execute("SELECT * FROM producto").fetchall()
    detalles = cur.execute("""
        SELECT detalle_compra.*, producto.nombre as producto
        FROM detalle_compra
        JOIN producto ON producto.id = detalle_compra.producto_id
    """).fetchall()

    conn.close()
    return render_template("compras.html",
                           compras=compras,
                           proveedores=proveedores,
                           productos=productos,
                           detalles=detalles)

# =========================
# CONFIRMAR COMPRA
# =========================

@app.route("/confirmar_compra", methods=["POST"])
def confirmar_compra():
    conn = get_db()
    cur = conn.cursor()

    compra_id = request.form["compra_id"].strip().lower()

    compra = cur.execute("SELECT * FROM compra WHERE id=?", (compra_id,)).fetchone()
    if not compra or compra["estado"] != "borrador":
        return redirect("/compras")

    detalles = cur.execute("SELECT * FROM detalle_compra WHERE compra_id=?", (compra_id,)).fetchall()
    if not detalles:
        return redirect("/compras")

    total = 0
    for d in detalles:
        total += d["cantidad"] * d["precio_compra"]
        cur.execute("UPDATE producto SET stock = stock + ? WHERE id=?",
                    (d["cantidad"], d["producto_id"]))

    cur.execute("UPDATE compra SET total=?, estado='confirmada' WHERE id=?",
                (total, compra_id))

    conn.commit()
    conn.close()
    return redirect("/compras")

# =========================
# VENTAS
# =========================

@app.route("/ventas", methods=["GET", "POST"])
def ventas():
    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST" and request.form.get("crear_documento"):
        cur.execute("""
            INSERT INTO venta (fecha, total, estado)
            VALUES (?, 0, 'borrador')
        """, (date.today(),))
        conn.commit()
        return redirect("/ventas")

    if request.method == "POST" and request.form.get("agregar_detalle"):
        venta_id = request.form["venta_id"].strip().lower()
        producto_id = request.form["producto_id"].strip().lower()
        cantidad = request.form["cantidad"].strip().lower()
        precio_venta = request.form["precio_venta"].strip().lower()

        if not cantidad.isdigit():
            return redirect("/ventas")

        cantidad = int(cantidad)
        if cantidad <= 0:
            return redirect("/ventas")

        if not precio_venta.isdigit():
            return redirect("/ventas")

        precio_venta = int(precio_venta)
        if precio_venta <= 0:
            return redirect("/ventas")

        producto = cur.execute("SELECT stock FROM producto WHERE id=?",
                               (producto_id,)).fetchone()

        if not producto or cantidad > producto["stock"]:
            return redirect("/ventas")

        estado = cur.execute("SELECT estado FROM venta WHERE id=?", (venta_id,)).fetchone()
        if not estado or estado["estado"] != "borrador":
            return redirect("/ventas")

        cur.execute("""
            INSERT INTO detalle_venta (venta_id, producto_id, cantidad, precio_venta, fecha)
            VALUES (?, ?, ?, ?, ?)
        """, (venta_id, producto_id, cantidad, precio_venta, date.today()))

        conn.commit()
        return redirect("/ventas")

    ventas = cur.execute("SELECT * FROM venta ORDER BY id DESC").fetchall()
    productos = cur.execute("SELECT * FROM producto").fetchall()
    detalles = cur.execute("""
        SELECT detalle_venta.*, producto.nombre as producto
        FROM detalle_venta
        JOIN producto ON producto.id = detalle_venta.producto_id
    """).fetchall()

    conn.close()
    return render_template("ventas.html",
                           ventas=ventas,
                           productos=productos,
                           detalles=detalles)

# =========================
# CONFIRMAR VENTA
# =========================

@app.route("/confirmar_venta", methods=["POST"])
def confirmar_venta():
    conn = get_db()
    cur = conn.cursor()

    venta_id = request.form["venta_id"].strip().lower()

    venta = cur.execute("SELECT * FROM venta WHERE id=?", (venta_id,)).fetchone()
    if not venta or venta["estado"] != "borrador":
        return redirect("/ventas")

    detalles = cur.execute("SELECT * FROM detalle_venta WHERE venta_id=?", (venta_id,)).fetchall()
    if not detalles:
        return redirect("/ventas")

    total = 0
    for d in detalles:
        producto = cur.execute("SELECT stock FROM producto WHERE id=?",
                               (d["producto_id"],)).fetchone()

        if d["cantidad"] > producto["stock"]:
            return redirect("/ventas")

        total += d["cantidad"] * d["precio_venta"]
        cur.execute("UPDATE producto SET stock = stock - ? WHERE id=?",
                    (d["cantidad"], d["producto_id"]))

    cur.execute("UPDATE venta SET total=?, estado='confirmada' WHERE id=?",
                (total, venta_id))

    conn.commit()
    conn.close()
    return redirect("/ventas")

# =========================
# INVENTARIO
# =========================

@app.route("/inventario")
def inventario():
    conn = get_db()
    cur = conn.cursor()

    inventario = cur.execute("""
        SELECT producto.*, categoria.nombre as categoria
        FROM producto
        LEFT JOIN categoria ON categoria.id = producto.categoria_id
        ORDER BY categoria.nombre
    """).fetchall()

    conn.close()
    return render_template("inventario.html", inventario=inventario)

# =========================
# MOVIMIENTOS
# =========================

@app.route("/movimientos")
def movimientos():
    conn = get_db()
    cur = conn.cursor()

    entradas = cur.execute("""
        SELECT 'entrada' as tipo, producto.nombre, cantidad, fecha, compra_id as documento
        FROM detalle_compra
        JOIN producto ON producto.id = detalle_compra.producto_id
    """).fetchall()

    salidas = cur.execute("""
        SELECT 'salida' as tipo, producto.nombre, cantidad, fecha, venta_id as documento
        FROM detalle_venta
        JOIN producto ON producto.id = detalle_venta.producto_id
    """).fetchall()

    movimientos = list(entradas) + list(salidas)

    conn.close()
    return render_template("movimientos.html", movimientos=movimientos)

# =========================
# ANALITICA
# =========================

@app.route("/analitica")
def analitica():

    conn = get_db()
    cur = conn.cursor()

    compras = cur.execute(
        "SELECT SUM(total) FROM compra WHERE estado='confirmada'"
    ).fetchone()[0] or 0

    ventas = cur.execute(
        "SELECT SUM(total) FROM venta WHERE estado='confirmada'"
    ).fetchone()[0] or 0

    margen = ventas - compras
    rotacion = 0

    proveedores = cur.execute("""
        SELECT proveedor.nombre,
               SUM(compra.total) total
        FROM compra
        JOIN proveedor
        ON proveedor.id = compra.proveedor_id
        WHERE compra.estado='confirmada'
        GROUP BY proveedor.id
    """).fetchall()

    proveedores = [dict(row) for row in proveedores]

    top_productos = cur.execute("""
        SELECT producto.nombre,
               SUM(detalle_venta.cantidad) total
        FROM detalle_venta
        JOIN producto
        ON producto.id = detalle_venta.producto_id
        GROUP BY producto.id
        ORDER BY total DESC
        LIMIT 5
    """).fetchall()

    top_productos = [dict(row) for row in top_productos]

    categorias = cur.execute("""
        SELECT categoria.nombre,
               SUM(producto.precio_venta * producto.stock) total
        FROM producto
        LEFT JOIN categoria
        ON categoria.id = producto.categoria_id
        GROUP BY categoria.id
    """).fetchall()

    categorias = [dict(row) for row in categorias]

    ventas_mes = cur.execute("""
        SELECT strftime('%Y-%m', fecha) mes,
               SUM(total) total
        FROM venta
        WHERE estado='confirmada'
        GROUP BY strftime('%Y-%m', fecha)
        ORDER BY mes
    """).fetchall()

    ventas_mes = [dict(row) for row in ventas_mes]

    conn.close()

    if categorias:
        max_categoria = max(
            [c["total"] if c["total"] else 0 for c in categorias]
        )
    else:
        max_categoria = 1

    if max_categoria == 0:
        max_categoria = 1

    return render_template(
        "analitica.html",
        compras=compras,
        ventas=ventas,
        margen=margen,
        rotacion=rotacion,
        proveedores=proveedores,
        top_productos=top_productos,
        categorias=categorias,
        ventas_mes=ventas_mes,
        max_categoria=max_categoria
    )

if __name__ == "__main__":
    app.run(debug=True)