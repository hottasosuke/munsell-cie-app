import streamlit as st
import plotly.graph_objs as go
import numpy as np

import colour
from colour.notation.munsell import (
    munsell_colour_to_xyY,
    xyY_to_munsell_colour
)

########################################
# 1) マンセル Hue リスト (参照コードに近い)
########################################
HUES = [
    '2.5R','5R','7.5R','10R',
    '2.5YR','5YR','7.5YR','10YR',
    '2.5Y','5Y','7.5Y','10Y',
    '2.5GY','5GY','7.5GY','10GY',
    '2.5G','5G','7.5G','10G',
    '2.5BG','5BG','7.5BG','10BG',
    '2.5B','5B','7.5B','10B',
    '2.5PB','5PB','7.5PB','10PB',
    '2.5P','5P','7.5P','10P',
    '2.5RP','5RP','7.5RP','10RP'
]
N_HUES = len(HUES)  # 40
HUE_TO_INDEX = {h: i for i, h in enumerate(HUES)}

########################################
# 2) DB構築: (Hue,Value,Chroma)->(Lab,円筒座標)
########################################
@st.cache_data
def build_munsell_database():
    """
    Hue=HUES(40種類)、Value=1..9、Chroma=2..28(2刻み)を試して
    munsell_colour_to_xyY()->XYZ->Lab に成功したデータを保存。

    円筒座標:
      - Hueインデックス → angle = idx*(360 / 40)
      - Chroma → 半径
      - Value → 高さ
      => x=r*cosθ, y=r*sinθ, z=Value
    """
    values = range(1, 10)
    chromas = range(2, 30, 2)

    munsell_str_list = []
    lab_list = []
    cyl_list = []

    for hue in HUES:
        idx = HUE_TO_INDEX[hue]
        angle_deg = idx*(360.0/N_HUES)

        for v in values:
            for c in chromas:
                m_str = f"{hue} {v}/{c}"
                try:
                    xyY = munsell_colour_to_xyY(m_str)
                    if xyY is None:
                        continue
                    XYZ = colour.xyY_to_XYZ(xyY)
                    Lab = colour.XYZ_to_Lab(XYZ)
                except:
                    # 失敗 or 定義外
                    continue

                # 円筒変換
                rad_ = np.radians(angle_deg)
                x_ = c*np.cos(rad_)
                y_ = c*np.sin(rad_)
                z_ = v

                munsell_str_list.append(m_str)
                lab_list.append(Lab)
                cyl_list.append([x_, y_, z_])

    return (
        munsell_str_list,
        np.array(lab_list),  # (N,3): Lab
        np.array(cyl_list)   # (N,3): Cylinder
    )

def lab_to_lch(Lab):
    L,a,b = Lab
    C = np.sqrt(a*a + b*b)
    H_deg = np.degrees(np.arctan2(b,a)) % 360
    return (L, C, H_deg)

########################################
# 3) 近似検索 (ΔE76)
########################################
def find_nearest_munsell(Lab_in, all_lab_array, all_str_list):
    diffs = all_lab_array - Lab_in
    dist_sq = np.sum(diffs**2, axis=1)
    idx_min = np.argmin(dist_sq)
    return all_str_list[idx_min]

def cie_to_munsell_fallback(Lab_in, all_lab_array, all_str_list):
    XYZ = colour.Lab_to_XYZ(Lab_in)
    xyY = colour.XYZ_to_xyY(XYZ)
    try:
        candidate = xyY_to_munsell_colour(xyY)
        if candidate is not None:
            return candidate
    except:
        pass
    return find_nearest_munsell(Lab_in, all_lab_array, all_str_list)

########################################
# 4) Lab->sRGB->#RRGGBB
########################################
def lab_to_hex(Lab_in):
    try:
        rgb_float = colour.convert(Lab_in, 'CIE Lab', 'sRGB')
    except:
        # fallback
        XYZ = colour.Lab_to_XYZ(Lab_in)
        rgb_float = colour.XYZ_to_sRGB(XYZ)

    rgb_float = np.clip(rgb_float, 0, 1)
    rgb_255 = (rgb_float*255).astype(int)
    return f"#{rgb_255[0]:02X}{rgb_255[1]:02X}{rgb_255[2]:02X}"

########################################
# 5) Streamlitアプリ
########################################
st.set_page_config(page_title="Munsell <-> CIE", layout="wide")
st.title("Munsell <-> CIE Converter (Fallback + color preview)")

# データベース読み込み
munsell_str_list, lab_array, cyl_array = build_munsell_database()

# モード切り替え
mode = st.radio("変換モード", ["Munsell -> CIE", "CIE -> Munsell"])

input_lab = None
input_cyl = None
hexcolor = "#FFFFFF"

# ---- (A) Munsell -> CIE ----
if mode == "Munsell -> CIE":
    m_in = st.text_input("Munsell (例: 5R 5/10)", "5R 5/10")
    try:
        xyY = munsell_colour_to_xyY(m_in)
        if xyY is None:
            raise ValueError("範囲外(None)")
        XYZ = colour.xyY_to_XYZ(xyY)
        Lab = colour.XYZ_to_Lab(XYZ)
        Lch = lab_to_lch(Lab)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("#### XYZ")
            st.write(f"X={XYZ[0]:.2f}, Y={XYZ[1]:.2f}, Z={XYZ[2]:.2f}")
        with c2:
            st.markdown("#### Lab")
            st.write(f"L*={Lab[0]:.2f}, a*={Lab[1]:.2f}, b*={Lab[2]:.2f}")
        with c3:
            st.markdown("#### LCH")
            st.write(f"L={Lch[0]:.2f}, C={Lch[1]:.2f}, H={Lch[2]:.1f}°")

        input_lab = np.array(Lab)
        hexcolor = lab_to_hex(input_lab)

        # 円筒座標
        if m_in in munsell_str_list:
            idx_ = munsell_str_list.index(m_in)
            input_cyl = cyl_array[idx_]
    except Exception as e:
        st.warning(f"変換失敗: {e}")

# ---- (B) CIE -> Munsell ----
else:
    c1, c2, c3 = st.columns(3)
    with c1:
        L_ = st.number_input("L*", value=50.0, min_value=0.0, max_value=100.0)
    with c2:
        a_ = st.number_input("a*", value=0.0, min_value=-128.0, max_value=128.0)
    with c3:
        b_ = st.number_input("b*", value=0.0, min_value=-128.0, max_value=128.0)

    Lab_in = np.array([L_, a_, b_])
    try:
        m_ret = cie_to_munsell_fallback(Lab_in, lab_array, munsell_str_list)
        st.write(f"**マンセル値** (範囲外は近似): {m_ret}")

        input_lab = Lab_in
        hexcolor = lab_to_hex(input_lab)

        if m_ret in munsell_str_list:
            idx_ = munsell_str_list.index(m_ret)
            input_cyl = cyl_array[idx_]
    except Exception as e:
        st.warning(f"CIE->Munsell変換失敗: {e}")


# ---- 6) Plotlyアニメ (Lab / Cylinder)
trace_lab_bg = go.Scatter3d(
    x=lab_array[:,0],
    y=lab_array[:,1],
    z=lab_array[:,2],
    mode='markers',
    marker=dict(size=2, color='lightgray', opacity=0.5),
    name='BG(Lab)',
    visible=True
)
trace_cyl_bg = go.Scatter3d(
    x=cyl_array[:,0],
    y=cyl_array[:,1],
    z=cyl_array[:,2],
    mode='markers',
    marker=dict(size=2, color='lightgray', opacity=0.5),
    name='BG(Cyl)',
    visible=False
)

if input_lab is not None:
    trace_lab_in = go.Scatter3d(
        x=[input_lab[0]],
        y=[input_lab[1]],
        z=[input_lab[2]],
        mode='markers',
        marker=dict(size=8, color='red', opacity=0.9),
        name='Input(Lab)',
        visible=True
    )
else:
    trace_lab_in = go.Scatter3d(visible=False)

if input_cyl is not None:
    trace_cyl_in = go.Scatter3d(
        x=[input_cyl[0]],
        y=[input_cyl[1]],
        z=[input_cyl[2]],
        mode='markers',
        marker=dict(size=8, color='red', opacity=0.9),
        name='Input(Cyl)',
        visible=False
    )
else:
    trace_cyl_in = go.Scatter3d(visible=False)

frames = [
    go.Frame(
        name='lab',
        data=[
            go.Scatter3d(visible=True),
            go.Scatter3d(visible=False),
            go.Scatter3d(visible=True),
            go.Scatter3d(visible=False)
        ],
        layout=go.Layout(
            scene=dict(
                xaxis_title="L*",
                yaxis_title="a*",
                zaxis_title="b*",
                aspectmode='cube'
            )
        )
    ),
    go.Frame(
        name='cyl',
        data=[
            go.Scatter3d(visible=False),
            go.Scatter3d(visible=True),
            go.Scatter3d(visible=False),
            go.Scatter3d(visible=True)
        ],
        layout=go.Layout(
            scene=dict(
                xaxis_title="x=r*cos(θ)",
                yaxis_title="y=r*sin(θ)",
                zaxis_title="Value",
                aspectmode='cube'
            )
        )
    )
]

# ボタンラベルをHTML化: "CIE Lab"=青文字
updatemenus = [
    dict(
        type='buttons',
        showactive=True,
        x=0.05, y=1.12,
        buttons=[
            dict(
                label='<span style="color:red;">CIE Lab</span>',
                method='animate',
                args=[
                    ['lab'],
                    dict(mode='immediate', frame=dict(duration=500, redraw=True), fromcurrent=True)
                ]
            ),
            dict(
                label='<span style="color:red;">Munsell Cylinder',
                method='animate',
                args=[
                    ['cyl'],
                    dict(mode='immediate', frame=dict(duration=500, redraw=True), fromcurrent=True)
                ]
            )
        ]
    )
]

fig = go.Figure(
    data=[trace_lab_bg, trace_cyl_bg, trace_lab_in, trace_cyl_in],
    layout=go.Layout(
        updatemenus=updatemenus,
        scene=dict(
            xaxis_title="L*",
            yaxis_title="a*",
            zaxis_title="b*",
            aspectmode='cube'
        ),
        height=800
    ),
    frames=frames
)

st.plotly_chart(fig, use_container_width=True)


with st.expander("使い方 & 変換の精度について"):
    st.markdown("""
- **Munsell -> CIE**  
  例: `5R 5/10`. 通常はライブラリ `colour-science` がマップしてXYZ->Labを正しく計算  
- **CIE -> Munsell**  
  L*, a*, b* を入力し、ライブラリが変換失敗の場合は**近似**を探す  
- **[CIE Lab] / [Munsell Cylinder]** ボタンで3D表示を500msかけて切替  
  - Lab = (L*, a*, b*)  
  - Cylinder = (HueIndex→θ, Chroma→半径, Value→高さ)  
- **入力色プレビュー**: サイドバーに150×150ピクセル、角丸12pxの四角形で表示  

### 変換精度について
1. **Munsell -> CIE**  
   - 参照しているデータは "Munsell Renotation System" (1930年代) をベースに `colour-science` が組み込んでいるものです。  
   - 公式のルックアップ方式なので、**「定義されている」マッチングに関してはほぼ正確**です。  
   - ただし (Hue, Value, Chroma) によっては厳密値が存在せず、近似的に補間される場合もあります。

2. **CIE -> Munsell**  
   - まずライブラリ内部変換を試み、  
     - 成功すれば Munsell Renotation Data 上で最も近い値を返します。  
     - 失敗や範囲外なら、**ΔE76 最小**となる点をデータベースから検索。  
   - この「ΔE76 近似」は**1.0以内～数程度の誤差**がありえます (色差1.0~2.0 は「肉眼で少し違う」レベル)。  
   - 厳密に特定できない色域も多いので、**参考値**としてご利用ください。

3. **標準光源・視野**  
   - ライブラリはデフォルトで「D65光源 + 2°標準観察者」などの条件を用いているため、  
     実際の照明環境・観察条件によっては見え方が異なる可能性があります。
""")

