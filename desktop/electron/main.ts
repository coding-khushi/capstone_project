import { app, BrowserWindow, globalShortcut, Tray, Menu, ipcMain, screen, desktopCapturer, nativeImage } from 'electron'
import path from 'path'

const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged

let mainWindow: BrowserWindow | null = null
let tray: Tray | null = null

function createWindow() {
  const { width: screenWidth, height: screenHeight } = screen.getPrimaryDisplay().workAreaSize

  mainWindow = new BrowserWindow({
    width: 400,
    height: 560,
    x: screenWidth - 420,
    y: screenHeight - 600,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    skipTaskbar: true,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist-renderer/index.html'))
  }

  mainWindow.on('blur', () => {
    // Keep window visible when it loses focus (user may click elsewhere)
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

function createTray() {
  // Use a simple colored square as the tray icon for now
  const icon = nativeImage.createEmpty()
  tray = new Tray(icon)

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Show Percept',
      click: () => toggleWindow(),
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => app.quit(),
    },
  ])

  tray.setToolTip('Percept')
  tray.setContextMenu(contextMenu)
  tray.on('click', () => toggleWindow())
}

function toggleWindow() {
  if (!mainWindow) return

  if (mainWindow.isVisible()) {
    mainWindow.hide()
  } else {
    positionWindow()
    mainWindow.show()
    mainWindow.focus()
  }
}

function positionWindow() {
  if (!mainWindow) return
  const { width: screenWidth, height: screenHeight } = screen.getPrimaryDisplay().workAreaSize
  mainWindow.setPosition(screenWidth - 420, screenHeight - 600)
}

// IPC: capture screenshot
ipcMain.handle('capture-screen', async () => {
  try {
    // Hide window so it doesn't appear in the screenshot
    mainWindow?.hide()
    await new Promise(resolve => setTimeout(resolve, 300))

    const sources = await desktopCapturer.getSources({
      types: ['screen'],
      thumbnailSize: { width: 1920, height: 1080 },
    })

    // Show window again
    mainWindow?.show()

    if (sources.length === 0) return { success: false, error: 'No screen sources found' }

    const primarySource = sources[0]
    const dataURL = primarySource.thumbnail.toDataURL()
    return { success: true, dataURL }
  } catch (err) {
    mainWindow?.show()
    return { success: false, error: String(err) }
  }
})

// IPC: hide window
ipcMain.handle('hide-window', () => {
  mainWindow?.hide()
})

// IPC: get window state
ipcMain.handle('get-window-state', () => ({
  isVisible: mainWindow?.isVisible() ?? false,
}))

app.whenReady().then(() => {
  createWindow()
  createTray()

  // Global shortcut: Ctrl+Shift+P (Windows/Linux) or Cmd+Shift+P (Mac)
  const shortcut = process.platform === 'darwin' ? 'Command+Shift+P' : 'Control+Shift+P'
  globalShortcut.register(shortcut, () => toggleWindow())

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

app.on('will-quit', () => {
  globalShortcut.unregisterAll()
})
