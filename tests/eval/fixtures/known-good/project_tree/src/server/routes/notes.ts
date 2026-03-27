let notes = []

export function registerNotesRoutes(app) {
  app.post('/notes', async (_req) => {
    const note = {
      id: 'note-1',
      text: 'fixture note',
      created_at: '2026-03-26T00:00:00+00:00',
    }
    notes.push(note)
    return note
  })

  app.get('/notes', async () => notes)
  app.delete('/notes/:id', async (req) => {
    notes = notes.filter((note) => note.id !== req.params.id)
    return { deleted: true }
  })
}
