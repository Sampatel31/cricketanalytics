import { z } from 'zod'

export const AuctionSessionSchema = z.object({
  franchise_name: z.string().min(1, 'Franchise name is required').max(100),
  budget_total: z.number().min(10).max(1000),
  format_type: z.enum(['T20I', 'ODI', 'TEST']),
  dna_id: z.string().optional(),
})

export type AuctionSessionFormData = z.infer<typeof AuctionSessionSchema>
