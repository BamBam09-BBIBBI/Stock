import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import io

st.set_page_config(
    page_title="ระบบวิเคราะห์ยอดขายและสั่งซื้อน้ำมันเครื่อง",
    page_icon="🛢️",
    layout="wide"
)

st.title("🛢️ ระบบวิเคราะห์ยอดขาย & แนะนำการสั่งซื้อประจำเดือน")
st.markdown("อัปโหลดไฟล์รายงาน 2 ไฟล์จากระบบ เพื่อดูแดชบอร์ดสรุปสินค้าขายดีและรายการแนะนำสั่งซื้ออัตโนมัติ")

# Sidebar for file upload
st.sidebar.header("📁 อัปโหลดไฟล์ประจำเดือน")
file_stock = st.sidebar.file_uploader("1. อัปโหลดไฟล์สต็อก (จัดการคลังสินค้า.xls)", type=['xls', 'xlsx'])
file_sales = st.sidebar.file_uploader("2. อัปโหลดไฟล์ยอดขาย (รายงานขนาดการขาย.xls)", type=['xls', 'xlsx'])

# Settings
st.sidebar.header("⚙️ ตั้งค่าเกณฑ์สั่งซื้อ")
lead_time_days = st.sidebar.slider("ระยะเวลารอของ (Lead Time: วัน)", min_value=1, max_value=14, value=3)

st.sidebar.subheader("🛡️ สต็อกสำรองกันขาด (Safety Stock)")
st.sidebar.caption("กำหนดจำนวนสต็อกขั้นต่ำแยกตามกลุ่มสินค้าและขนาด")
safety_filter = st.sidebar.slider("🔧 ไส้กรองน้ำมันเครื่อง / ไส้กรองทั่วไป (ลูก)", min_value=0, max_value=20, value=5, step=1)
safety_1L = st.sidebar.slider("🧴 ขนาด ≤ 1 ลิตร (ขวดเล็ก / เติม / มอเตอร์ไซค์)", min_value=0, max_value=24, value=6, step=1)
safety_4L = st.sidebar.slider("🛢️ ขนาด 4 ลิตร (แกลลอนเบนซิน)", min_value=0, max_value=12, value=3, step=1)
safety_6L = st.sidebar.slider("🚚 ขนาด 6 ลิตร (แกลลอนดีเซล)", min_value=0, max_value=12, value=4, step=1)
safety_other = st.sidebar.slider("📦 ขนาดอื่นๆ / ถังใหญ่ (18L, 20L)", min_value=0, max_value=5, value=1, step=1)

if file_stock is not None and file_sales is not None:
    try:
        # Load Stock
        df_stock = pd.read_excel(file_stock)
        
        # Load Sales (skip 2 header rows of Shell report)
        df_sales_raw = pd.read_excel(file_sales, skiprows=2)
        col_prod = df_sales_raw.columns[0]
        col_size = df_sales_raw.columns[1]
        col_total = df_sales_raw.columns[-1]
        
        sales_df = df_sales_raw[[col_prod, col_size, col_total]].copy()
        sales_df.columns = ['Product_Name', 'Size', 'Total_Sold_Liters']
        sales_df = sales_df.dropna(subset=['Product_Name'])
        sales_df['Product_Name'] = sales_df['Product_Name'].astype(str).str.strip()
        sales_df['Total_Sold_Liters'] = pd.to_numeric(sales_df['Total_Sold_Liters'], errors='coerce').fillna(0)
        
        # Group sales in case product appears more than once
        sales_grouped = sales_df.groupby('Product_Name', as_index=False)['Total_Sold_Liters'].sum()
        
        # Merge by Product Name
        df_merged = pd.merge(
            df_stock,
            sales_grouped,
            left_on=df_stock['ชื่อสินค้า'].astype(str).str.strip(),
            right_on=sales_grouped['Product_Name'].astype(str).str.strip(),
            how='left'
        )
        
        # Data preparation
        df_merged['Total_Sold_Liters'] = df_merged['Total_Sold_Liters'].fillna(0)
        df_merged['ขนาด(ลิตร)'] = pd.to_numeric(df_merged['ขนาด(ลิตร)'], errors='coerce').fillna(1.0)
        df_merged['จำนวนคงเหลือ/หน่วย'] = pd.to_numeric(df_merged['จำนวนคงเหลือ/หน่วย'], errors='coerce').fillna(0)
        
        # Flag oil filters
        is_filter = df_merged['ชื่อสินค้า'].str.contains('ไส้กรอง|กรอง', case=False, na=False) | df_merged['หมวดบริการ'].str.contains('กรอง', case=False, na=False)
        
        # Convert liters sold to units sold (Bottles/Gallons/Pieces)
        df_merged['Units_Sold'] = np.where(
            is_filter,
            df_merged['Total_Sold_Liters'],
            np.where(
                df_merged['ขนาด(ลิตร)'] > 0,
                np.round(df_merged['Total_Sold_Liters'] / df_merged['ขนาด(ลิตร)'], 1),
                df_merged['Total_Sold_Liters']
            )
        )
        
        # Assign Safety Stock: Priority 1 = Oil Filter, Priority 2 = Container size
        conditions_safety = [
            is_filter,
            (~is_filter) & (df_merged['ขนาด(ลิตร)'] <= 1.0),
            (~is_filter) & (df_merged['ขนาด(ลิตร)'] > 1.0) & (df_merged['ขนาด(ลิตร)'] <= 4.0),
            (~is_filter) & (df_merged['ขนาด(ลิตร)'] > 4.0) & (df_merged['ขนาด(ลิตร)'] <= 6.0),
            (~is_filter) & (df_merged['ขนาด(ลิตร)'] > 6.0)
        ]
        choices_safety = [safety_filter, safety_1L, safety_4L, safety_6L, safety_other]
        df_merged['Safety_Stock'] = np.select(conditions_safety, choices_safety, default=safety_other)
        
        # Calculations: ROP & Suggested Order
        df_merged['Daily_Units'] = df_merged['Units_Sold'] / 31.0
        df_merged['ROP'] = np.ceil((df_merged['Daily_Units'] * lead_time_days) + df_merged['Safety_Stock'])
        
        # Order Up To Level: Target 15 days supply + Safety Stock
        target_coverage_days = 15.0
        df_merged['Max_Stock'] = np.ceil((df_merged['Daily_Units'] * target_coverage_days) + df_merged['Safety_Stock'])
        
        df_merged['Suggested_Order'] = np.where(
            (df_merged['จำนวนคงเหลือ/หน่วย'] <= df_merged['ROP']) & (df_merged['Units_Sold'] > 0),
            np.maximum(0, np.ceil(df_merged['Max_Stock'] - df_merged['จำนวนคงเหลือ/หน่วย'])),
            0
        ).astype(int)
        
        # If out of stock but sold before, ensure ordering at least safety stock
        df_merged.loc[(df_merged['จำนวนคงเหลือ/หน่วย'] <= 0) & (df_merged['Units_Sold'] > 0) & (df_merged['Suggested_Order'] < df_merged['Safety_Stock']), 'Suggested_Order'] = df_merged['Safety_Stock']
        
        # Identify Top Sellers (Top 20% by sales)
        sales_threshold = df_merged[df_merged['Units_Sold'] > 0]['Units_Sold'].quantile(0.80) if len(df_merged[df_merged['Units_Sold'] > 0]) > 0 else 5.0
        df_merged['Is_Top_Seller'] = df_merged['Units_Sold'] >= sales_threshold
        
        # Status assignment with Hot-Item Alert
        conditions = [
            (df_merged['จำนวนคงเหลือ/หน่วย'] <= 0) & (df_merged['Is_Top_Seller']),
            (df_merged['จำนวนคงเหลือ/หน่วย'] <= 0) & (df_merged['Units_Sold'] > 0),
            (df_merged['จำนวนคงเหลือ/หน่วย'] <= df_merged['ROP']) & (df_merged['Is_Top_Seller']),
            (df_merged['จำนวนคงเหลือ/หน่วย'] <= df_merged['ROP']) & (df_merged['Units_Sold'] > 0),
            (df_merged['Units_Sold'] == 0) & (df_merged['จำนวนคงเหลือ/หน่วย'] > 0),
            (df_merged['จำนวนคงเหลือ/หน่วย'] > df_merged['ROP'])
        ]
        choices = [
            '🔥 ขายดีแต่ของหมด! (วิกฤต)',
            '🔴 สินค้าหมดสต็อก',
            '⚡ สินค้าขายดีต้องรีบสั่ง',
            '🚨 ต้องสั่งซื้อเพิ่ม',
            '🐢 ไม่เคลื่อนไหว (Dead Stock)',
            '🟢 สต็อกปกติ'
        ]
        df_merged['Status'] = np.select(conditions, choices, default='🟢 ปกติ')
        
        # Highlight Urgent Banner if top sellers are out of stock
        critical_out = df_merged[df_merged['Status'] == '🔥 ขายดีแต่ของหมด! (วิกฤต)']
        if len(critical_out) > 0:
            st.error(f"🚨 **แจ้งเตือนเร่งด่วน:** มีสินค้าขายดี **{len(critical_out)} รายการ** ที่สต็อกหมดเกลี้ยง (เสียโอกาสการขาย) ได้แก่: " + ", ".join(critical_out['ชื่อสินค้า'].tolist()))
        
        # KPI Row
        st.subheader("📊 สรุปภาพรวมประจำเดือน")
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        
        total_liters = df_merged['Total_Sold_Liters'].sum()
        total_units = df_merged['Units_Sold'].sum()
        need_order_count = len(df_merged[df_merged['Status'].str.contains('หมด|สั่ง', na=False)])
        dead_stock_count = len(df_merged[df_merged['Status'] == '🐢 ไม่เคลื่อนไหว (Dead Stock)'])
        
        kpi1.metric("ยอดขายรวม (ลิตร)", f"{total_liters:,.0f} ลิตร")
        kpi2.metric("ยอดขายรวม (ขวด/แกลลอน/ลูก)", f"{total_units:,.0f} ชิ้น")
        kpi3.metric("รายการต้องสั่งด่วน", f"{need_order_count} รายการ", delta=-need_order_count if need_order_count > 0 else 0, delta_color="inverse")
        kpi4.metric("สินค้าไม่มีการขาย (Dead Stock)", f"{dead_stock_count} รายการ")
        
        st.divider()
        
        # Chart Row
        col_chart1, col_chart2 = st.columns([6, 4])
        
        with col_chart1:
            st.markdown("### 🏆 10 อันดับสินค้าขายดีที่สุด (ยอดขาย: ลิตร/ชิ้น)")
            top10 = df_merged[df_merged['Units_Sold'] > 0].sort_values(by='Units_Sold', ascending=False).head(10)
            if len(top10) > 0:
                fig_bar = px.bar(
                    top10,
                    x='Units_Sold',
                    y='ชื่อสินค้า',
                    orientation='h',
                    text='Units_Sold',
                    color='Units_Sold',
                    color_continuous_scale='Reds'
                )
                fig_bar.update_layout(yaxis={'categoryorder':'total ascending'}, showlegend=False, height=450)
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.write("ไม่พบข้อมูลยอดขาย")
            
        with col_chart2:
            st.markdown("### 🎯 สัดส่วนสถานะสต็อกสินค้า")
            status_summary = df_merged['Status'].value_counts().reset_index()
            status_summary.columns = ['Status', 'Count']
            fig_pie = px.pie(
                status_summary,
                values='Count',
                names='Status',
                color='Status',
                color_discrete_map={
                    '🔥 ขายดีแต่ของหมด! (วิกฤต)': '#780000',
                    '🔴 สินค้าหมดสต็อก': '#e63946',
                    '⚡ สินค้าขายดีต้องรีบสั่ง': '#d97706',
                    '🚨 ต้องสั่งซื้อเพิ่ม': '#f4a261',
                    '🐢 ไม่เคลื่อนไหว (Dead Stock)': '#a8dadc',
                    '🟢 สต็อกปกติ': '#2a9d8f'
                }
            )
            fig_pie.update_layout(height=450)
            st.plotly_chart(fig_pie, use_container_width=True)
            
        st.divider()
        
        # Reorder Action Table
        st.subheader("📋 รายการที่ต้องเปิดบิลสั่งซื้อรอบนี้ (Action Order List)")
        order_list = df_merged[df_merged['Status'].str.contains('หมด|สั่ง', na=False)].copy()
        
        if len(order_list) > 0:
            # Sort by Critical status first, then Suggested Order
            order_list['Sort_Priority'] = np.where(order_list['Status'].str.contains('🔥'), 1, 2)
            order_list = order_list.sort_values(by=['Sort_Priority', 'Suggested_Order'], ascending=[True, False])
            
            order_table = order_list[['รหัสสินค้า', 'ชื่อสินค้า', 'ขนาด(ลิตร)', 'จำนวนคงเหลือ/หน่วย', 'Units_Sold', 'Safety_Stock', 'ROP', 'Suggested_Order', 'Status']]
            order_table.columns = ['รหัสสินค้า', 'ชื่อสินค้า', 'ขนาด(ลิตร)', 'สต็อกคงเหลือ', 'ยอดขายเดือนนี้ (ชิ้น)', 'สต็อกสำรอง (Safety)', 'จุดสั่งซื้อ (ROP)', 'จำนวนที่แนะนำให้สั่ง (ชิ้น)', 'สถานะ']
            
            st.dataframe(
                order_table.style.applymap(
                    lambda v: 'background-color: #ffcccc; font-weight: bold; color: #990000;' if '🔥' in str(v) else (
                        'background-color: #ffe6e6; color: #cc0000;' if '🔴' in str(v) else (
                            'background-color: #fff3cd; color: #856404;' if '⚡' in str(v) or '🚨' in str(v) else ''
                        )
                    ),
                    subset=['สถานะ']
                ),
                use_container_width=True
            )
            
            # Excel export
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                order_table.to_excel(writer, index=False, sheet_name='Action_Order_List')
            excel_data = output.getvalue()
            
            st.download_button(
                label="📥 ดาวน์โหลดใบสั่งซื้อ (Excel) เพื่อส่งเซลส์",
                data=excel_data,
                file_name="รายการสั่งซื้อน้ำมันเครื่องและไส้กรองประจำเดือน.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.success("🎉 สต็อกมีเพียงพอทุกรายการ ยังไม่มีรายการที่ต้องสั่งซื้อเพิ่มในรอบนี้!")
            
        # Dead Stock Section
        with st.expander("🔍 ดูรายการสินค้าที่ไม่มียอดขายในเดือนนี้ (Dead Stock / Slow-Moving)"):
            dead_df = df_merged[df_merged['Status'] == '🐢 ไม่เคลื่อนไหว (Dead Stock)'][['รหัสสินค้า', 'ชื่อสินค้า', 'ขนาด(ลิตร)', 'จำนวนคงเหลือ/หน่วย']].sort_values(by='จำนวนคงเหลือ/หน่วย', ascending=False)
            st.dataframe(dead_df, use_container_width=True)
            
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการประมวลผลไฟล์: {e}")
else:
    st.info("👈 กรุณาอัปโหลดไฟล์ 'จัดการคลังสินค้า.xls' และ 'รายงานขนาดการขาย.xls' ที่แถบเมนูด้านซ้ายเพื่อเริ่มประมวลผล")
