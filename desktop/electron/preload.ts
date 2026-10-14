import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('percept', {
  captureScreen: (): Promise<{ success: boolean; dataURL?: string; error?: string }> =>
    ipcRenderer.invoke('capture-screen'),

  hideWindow: (): Promise<void> =>
    ipcRenderer.invoke('hide-window'),

  getWindowState: (): Promise<{ isVisible: boolean }> =>
    ipcRenderer.invoke('get-window-state'),
})
