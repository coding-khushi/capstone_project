import { app, BrowserWindow, globalShortcut, Tray, Menu, ipcMain, screen, desktopCapturer, nativeImage, dialog } from 'electron'
import path from 'path'

const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged

let mainWindow: BrowserWindow | null = null
let tray: Tray | null = null

// Window sizes for the two UI states. When collapsed, the window shrinks to the
// floating button so its transparent area no longer blocks clicks on other apps.
const EXPANDED_SIZE = { width: 400, height: 560 }
const COLLAPSED_SIZE = { width: 210, height: 84 }

function createWindow() {
  const { width: screenWidth, height: screenHeight } = screen.getPrimaryDisplay().workAreaSize

  mainWindow = new BrowserWindow({
    width: EXPANDED_SIZE.width,
    height: EXPANDED_SIZE.height,
    x: screenWidth - EXPANDED_SIZE.width - 20,
    y: screenHeight - EXPANDED_SIZE.height - 40,
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

  // Exclude Percept's own panel from screen capture so recorded frames never
  // include its chat (Windows 10 2004+ and macOS).
  mainWindow.setContentProtection(true)

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
    // Show where the user last left it (no snapping back to the corner).
    mainWindow.show()
    mainWindow.focus()
  }
}

// Resize while keeping the bottom-right corner fixed, clamped to the screen,
// so the panel opens/closes in place wherever the user dragged the button.
function resizeAnchored(size: { width: number; height: number }) {
  if (!mainWindow) return
  const b = mainWindow.getBounds()
  const area = screen.getDisplayMatching(b).workArea
  let x = b.x + b.width - size.width
  let y = b.y + b.height - size.height
  x = Math.min(Math.max(x, area.x), area.x + area.width - size.width)
  y = Math.min(Math.max(y, area.y), area.y + area.height - size.height)
  mainWindow.setResizable(true)  // some platforms ignore setBounds on non-resizable windows
  mainWindow.setBounds({ x, y, width: size.width, height: size.height })
  mainWindow.setResizable(false)
}

// IPC: switch between the floating button (collapsed) and the full panel
ipcMain.handle('set-collapsed', (_event, collapsed: boolean) => {
  resizeAnchored(collapsed ? COLLAPSED_SIZE : EXPANDED_SIZE)
})

// IPC: capture screenshot
ipcMain.handle('capture-screen', async () => {
  try {
    // Hide window so it doesn't appear in the screenshot
    mainWindow?.hide()
    await new Promise(resolve => setTimeout(resolve, 500))

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

// IPC: get screen source ID for renderer-side MediaRecorder
ipcMain.handle('get-screen-source', async () => {
  try {
    const sources = await desktopCapturer.getSources({ types: ['screen'] })
    if (sources.length === 0) return { success: false, error: 'No screen sources found' }
    return { success: true, sourceId: sources[0].id }
  } catch (err) {
    return { success: false, error: String(err) }
  }
})

// IPC: open file picker dialog (for granting file access from suggestion banner)
ipcMain.handle('select-file', async (_event, hint?: string) => {
  const result = await dialog.showOpenDialog({
    properties: ['openFile'],
    defaultPath: hint ? path.dirname(hint) : app.getPath('home'),
    title: 'Select the file Percept can read',
  })
  if (result.canceled || result.filePaths.length === 0) return { path: null }
  return { path: result.filePaths[0] }
})

// IPC: open folder picker dialog for project selection
ipcMain.handle('select-folder', async () => {
  const result = await dialog.showOpenDialog({
    properties: ['openDirectory', 'createDirectory'],
    defaultPath: app.getPath('home'),
  })
  if (result.canceled || result.filePaths.length === 0) return { path: null }
  return { path: result.filePaths[0] }
})

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
