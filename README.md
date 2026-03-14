# 智慧監控系統儀表板 (Python Tkinter 版)

這是一個使用 Python Tkinter 開發的桌面應用程式，專為物聯網 (IoT) 監控設計。透過 MQTT 通訊協定，即時接收並記錄來自 ESP32 的溫濕度數據，並整合 Discord Webhook 提供警報回報功能。

## 🚀 核心功能
* **即時數據儀表板**：動態更新溫度與濕度數值。
* **動畫圖示**：包含動態水位波動與溫度計視覺效果，增加互動性。
* **即時圖表**：使用 Matplotlib 繪製最近 10 筆數據的趨勢圖。
* **LED 遠端控制**：提供按鈕介面，控制遠端設備的 LED 狀態（開啟、關閉、閃爍、定時）。
* **Discord 整合**：定時將溫濕度資訊發送至指定的 Discord 頻道。
* **數據匯出**：一鍵將歷史數據匯出為帶有 BOM (防止亂碼) 的 CSV 檔案。

## 🛠 使用技術
* **Python 3.x**
* **Tkinter**: GUI 介面設計
* **Matplotlib**: 動態數據圖表繪製
* **Paho-MQTT**: MQTT 客戶端連線
* **Requests**: Discord Webhook API 呼叫

搭配Wokwi線上模擬ESP32 https://wokwi.com/projects/458298760556964865
