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
default_safety_stock = st.sidebar.slider("สต็อกสำรองกันขาด (Safety Stock: แกลลอน/ขวด)", min_value=0, max_value=10, value=2)

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
        
        # Merge by Product Name
        df_merged = pd.merge(
            df_stock,
            sales_df[['Product_Name', 'Total_Sold_Liters']],
            left_on=df_stock['ชื่อสินค้า'].astype(str).str.strip(),
            right_on=sales_df['Product_Name'].astype(str).str.strip(),
            how='left'
        )
        
        # Data preparation
        df_merged['Total_Sold_Liters'] = df_merged['Total_Sold_Liters'].fillna(0)
        df_merged['ขนาด(ลิตร)'] = pd.to_numeric(df_merged['ขนาด(ลิตร)'], errors='coerce').fillna(1)
        df_merged['จำนวนคงเหลือ/หน่วย'] = pd.to_numeric(df_merged['จำนวนคงเหลือ/หน่วย'], errors='coerce').fillna(0)
        
        # Convert liters to units (e.g. 72 liters / 6L = 12 cans)
        df_merged['Units_Sold'] = np.where(
            df_merged['ขนาด(ลิตร)'] > 0,
            np.round(df_merged['Total_Sold_Liters'] / df_merged['ขนาด(ลิตร)'], 1),
            df_merged['Total_Sold_Liters']
        )
        
        # Calculations (ROP & Suggested Order)
        df_merged['Daily_Units'] = df_merged['Units_Sold'] / 31.0
        df_merged['ROP'] = (df_merged['Daily_Units'] * lead_time_days) + default_safety_stock
        df_merged['Suggested_Order'] = np.where(
            df_merged['จำนวนคงเหลือ/หน่วย'] <= df_merged['ROP'],
            np.maximum(0, np.ceil((df_merged['ROP'] * 2) - df_merged['จำนวนคงเหลือ/หน่วย'])),
            0
        ).astype(int)
        
        # Status assignment
        conditions = [
            (df_merged['จำนวนคงเหลือ/หน่วย'] <= 0) & (df_merged['Units_Sold'] > 0),
            (df_merged['จำนวนคงเหลือ/หน่วย'] <= df_merged['ROP']) & (df_merged['Units_Sold'] > 0),
            (df_merged['Units_Sold'] == 0) & (df_merged['จำนวนคงเหลือ/หน่วย'] > 0),
            (df_merged['จำนวนคงเหลือ/หน่วย'] > df_merged['ROP'])
        ]
        choices = [
            '🔴 สินค้าหมด (ขาดแคลน)',
            '🚨 ต้องสั่งซื้อเพิ่ม',
            '🐢 ไม่เคลื่อนไหว (Dead Stock)',
            '🟢 สต็อกปกติ'
        ]
        df_merged['Status'] = np.select(conditions, choices, default='🟢 ปกติ')
        
        # KPI Row
        st.subheader("📊 สรุปภาพรวมประจำเดือน")
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        
        total_liters = df_merged['Total_Sold_Liters'].sum()
        total_units = df_merged['Units_Sold'].sum()
        need_order_count = len(df_merged[df_merged['Status'].isin(['🔴 สินค้าหมด (ขาดแคลน)', '🚨 ต้องสั่งซื้อเพิ่ม'])])
        dead_stock_count = len(df_merged[df_merged['Status'] == '🐢 ไม่เคลื่อนไหว (Dead Stock)'])
        
        kpi1.metric("ยอดขายรวม (ลิตร)", f"{total_liters:,.0f} ลิตร")
        kpi2.metric("ยอดขายรวม (ขวด/แกลลอน)", f"{total_units:,.0f} ชิ้น")
        kpi3.metric("รายการต้องสั่งด่วน", f"{need_order_count} รายการ", delta=-need_order_count if need_order_count > 0 else 0, delta_color="inverse")
        kpi4.metric("สินค้าไม่มีการขาย (Dead Stock)", f"{dead_stock_count} รายการ")
        
        st.divider()
        
        # Chart Row
        col_chart1, col_chart2 = st.columns([6, 4])
        
        with col_chart1:
            st.markdown("### 🏆 10 อันดับสินค้าขายดีที่สุด (ยอดขาย: ลิตร)")
            top10 = df_merged.sort_values(by='Total_Sold_Liters', ascending=False).head(10)
            fig_bar = px.bar(
                top10,
                x='Total_Sold_Liters',
                y='ชื่อสินค้า',
                orientation='h',
                text='Total_Sold_Liters',
                color='Total_Sold_Liters',
                color_continuous_scale='Reds'
            )
            fig_bar.update_layout(yaxis={'categoryorder':'total ascending'}, showlegend=False, height=450)
            st.plotly_chart(fig_bar, use_container_width=True)
            
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
                    '🔴 สินค้าหมด (ขาดแคลน)': '#e63946',
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
        order_list = df_merged[df_merged['Status'].isin(['🔴 สินค้าหมด (ขาดแคลน)', '🚨 ต้องสั่งซื้อเพิ่ม'])].copy()
        
        if len(order_list) > 0:
            order_table = order_list[['รหัสสินค้า', 'ชื่อสินค้า', 'ขนาด(ลิตร)', 'จำนวนคงเหลือ/หน่วย', 'Units_Sold', 'ROP', 'Suggested_Order', 'Status']].sort_values(by='Suggested_Order', ascending=False)
            order_table.columns = ['รหัสสินค้า', 'ชื่อสินค้า', 'ขนาด(ลิตร)', 'สต็อกคงเหลือ', 'ยอดขายเดือนนี้ (ชิ้น)', 'จุดสั่งซื้อ (ROP)', 'จำนวนที่แนะนำให้สั่ง (ชิ้น)', 'สถานะ']
            st.dataframe(order_table, use_container_width=True)
            
            # Excel export
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                order_table.to_excel(writer, index=False, sheet_name='Action_Order_List')
            excel_data = output.getvalue()
            
            st.download_button(
                label="📥 ดาวน์โหลดใบสั่งซื้อ (Excel) เพื่อส่งเซลส์",
                data=excel_data,
                file_name="รายการสั่งซื้อน้ำมันเครื่องประจำเดือน.xlsx",
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
