

class ChainProtocol(Protocol, ABC):

    @classmethod
    def configure_protocol(
            cls,
            headerdb: BaseAsyncHeaderDB,
            network_id: int,
            vm_configuration: Tuple[Tuple[int, Type[BaseVM]], ...]) -> Type[ChainProtocol]:
        return type(
            f'{cls.__name__}Network{network_id}',
            (cls, ),
            dict(
                headerdb=headerdb,
                network_id=network_id,
                vm_configuration=vm_configuration,
            ),
        )

    @abstractmethod
    @property
    def headerdb(self):
        pass

    @abstractmethod
    @property
    def network_id(self):
        pass

    @abstractmethod
    @property
    def vm_configuration(self):
        pass

    @property
    async def genesis(self) -> BlockHeader:
        genesis_hash = await self.wait(
            self.headerdb.coro_get_canonical_block_hash(BlockNumber(GENESIS_BLOCK_NUMBER)))
        return await self.wait(self.headerdb.coro_get_block_header_by_hash(genesis_hash))

    @property
    async def _local_chain_info(self) -> ChainInfo:
        genesis = await self.genesis
        head = await self.wait(self.headerdb.coro_get_canonical_head())
        total_difficulty = await self.headerdb.coro_get_score(head.hash)
        return ChainInfo(
            block_number=head.block_number,
            block_hash=head.hash,
            total_difficulty=total_difficulty,
            genesis_hash=genesis.hash,
        )

