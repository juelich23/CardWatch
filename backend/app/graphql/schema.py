"""
GraphQL Schema
Combines queries and mutations into the main schema
"""
import strawberry
from app.graphql.queries import Query
from app.graphql.mutations import Mutation


schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
)
