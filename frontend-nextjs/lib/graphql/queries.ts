import { gql } from '@apollo/client';

export const GET_AUCTION_ITEMS = gql`
  query GetAuctionItems(
    $page: Int!
    $pageSize: Int!
    $auctionHouse: String
    $category: String
    $gradingCompany: String
    $sport: String
    $search: String
    $minBid: Float
    $maxBid: Float
    $status: String
  ) {
    auctionItems(
      page: $page
      pageSize: $pageSize
      auctionHouse: $auctionHouse
      category: $category
      gradingCompany: $gradingCompany
      sport: $sport
      search: $search
      minBid: $minBid
      maxBid: $maxBid
      status: $status
    ) {
      items {
        id
        title
        description
        currentBid
        startingBid
        bidCount
        endTime
        imageUrl
        itemUrl
        auctionHouse
        lotNumber
        gradingCompany
        grade
        certNumber
        category
        sport
        status
        isWatched
      }
      total
      page
      pageSize
      hasMore
    }
  }
`;

export const GET_AUCTION_ITEM = gql`
  query GetAuctionItem($id: Int!) {
    auctionItem(id: $id) {
      id
      title
      description
      currentBid
      startingBid
      bidCount
      endTime
      imageUrl
      itemUrl
      auctionHouse
      lotNumber
      gradingCompany
      grade
      certNumber
      category
      status
      isWatched
      altPriceEstimate
    }
  }
`;

export const GET_MARKET_VALUE_ESTIMATE = gql`
  query GetMarketValueEstimate($itemId: Int!) {
    marketValueEstimate(itemId: $itemId) {
      estimatedLow
      estimatedHigh
      estimatedAverage
      confidence
      notes
    }
  }
`;

export const GET_AUCTION_HOUSES = gql`
  query GetAuctionHouses {
    auctionHouses
  }
`;

export const GET_CATEGORIES = gql`
  query GetCategories($auctionHouse: String) {
    categories(auctionHouse: $auctionHouse)
  }
`;

export const TOGGLE_WATCH = gql`
  mutation ToggleWatch($itemId: Int!) {
    toggleWatch(itemId: $itemId) {
      success
      message
    }
  }
`;

export const GET_WATCHLIST = gql`
  query GetWatchlist($includeEnded: Boolean!, $page: Int!, $pageSize: Int!) {
    watchlist(includeEnded: $includeEnded, page: $page, pageSize: $pageSize) {
      items {
        id
        title
        description
        currentBid
        startingBid
        bidCount
        endTime
        imageUrl
        itemUrl
        auctionHouse
        lotNumber
        gradingCompany
        grade
        certNumber
        category
        status
        isWatched
      }
      total
      page
      pageSize
      hasMore
    }
  }
`;

export const GET_PRICE_HISTORY = gql`
  query GetPriceHistory($itemId: Int!, $days: Int) {
    priceHistory(itemId: $itemId, days: $days) {
      snapshotDate
      currentBid
      bidCount
      status
    }
  }
`;
