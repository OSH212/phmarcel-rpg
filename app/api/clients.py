"""
Client API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.client import Client
from app.schemas.client import ClientCreate, ClientResponse

router = APIRouter()


@router.post("", response_model=ClientResponse, status_code=201)
async def create_client(
    client_data: ClientCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new client.

    Args:
        client_data: Client creation data (name, email, complexity)
        db: Database session

    Returns:
        ClientResponse with created client data

    Raises:
        HTTPException 409: If client with same email already exists
    """
    result = await db.execute(
        select(Client).where(Client.email == client_data.email.lower())
    )
    existing_client = result.scalar_one_or_none()

    if existing_client:
        raise HTTPException(
            status_code=409,
            detail=f"Client with email {client_data.email} already exists"
        )

    new_client = Client(
        name=client_data.name,
        email=client_data.email.lower(),
        complexity=client_data.complexity
    )

    db.add(new_client)
    await db.flush()
    await db.refresh(new_client)

    return new_client

