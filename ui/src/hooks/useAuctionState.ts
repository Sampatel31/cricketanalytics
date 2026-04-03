import { useAuctionStore } from '../store/auction.store'

export function useAuctionState() {
  return useAuctionStore()
}
