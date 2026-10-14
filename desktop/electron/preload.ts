import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('percept', {
  captureScreen: (): Promise<{ success: boolean; dataURL?: string; error?: string }> =>
    ipcRenderer.invoke('capture-screen'),

  getScreenSource: (): Promise<{ success: boolean; sourceId?: string; error?: string }> =>
    ipcRenderer.invoke('get-screen-source'),

  selectFolder: (): Promise<{ path: string | null }> =>
    ipcRenderer.invoke('select-folder'),

  hideWindow: (): Promise<void> =>
    ipcRenderer.invoke('hide-window'),

  getWindowState: (): Promise<{ isVisible: boolean }> =>
    ipcRenderer.invoke('get-window-state'),
})
