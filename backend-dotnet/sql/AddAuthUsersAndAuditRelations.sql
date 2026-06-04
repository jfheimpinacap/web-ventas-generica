IF OBJECT_ID(N'[__EFMigrationsHistory]') IS NULL
BEGIN
    CREATE TABLE [__EFMigrationsHistory] (
        [MigrationId] nvarchar(150) NOT NULL,
        [ProductVersion] nvarchar(32) NOT NULL,
        CONSTRAINT [PK___EFMigrationsHistory] PRIMARY KEY ([MigrationId])
    );
END;
GO

BEGIN TRANSACTION;
GO

CREATE TABLE [Brands] (
    [Id] int NOT NULL IDENTITY,
    [Name] nvarchar(120) NOT NULL,
    [Slug] nvarchar(140) NOT NULL,
    [Logo] nvarchar(500) NULL,
    [Description] nvarchar(max) NOT NULL DEFAULT N'',
    [IsActive] bit NOT NULL DEFAULT CAST(1 AS bit),
    [CreatedAt] datetimeoffset NOT NULL DEFAULT (SYSUTCDATETIME()),
    [UpdatedAt] datetimeoffset NOT NULL DEFAULT (SYSUTCDATETIME()),
    [CreatedById] int NULL,
    [UpdatedById] int NULL,
    CONSTRAINT [PK_Brands] PRIMARY KEY ([Id])
);
GO

CREATE TABLE [Categories] (
    [Id] int NOT NULL IDENTITY,
    [Name] nvarchar(120) NOT NULL,
    [Slug] nvarchar(140) NOT NULL,
    [ParentId] int NULL,
    [Description] nvarchar(max) NOT NULL DEFAULT N'',
    [IsActive] bit NOT NULL DEFAULT CAST(1 AS bit),
    [Order] int NOT NULL DEFAULT 0,
    [CreatedAt] datetimeoffset NOT NULL DEFAULT (SYSUTCDATETIME()),
    [UpdatedAt] datetimeoffset NOT NULL DEFAULT (SYSUTCDATETIME()),
    [CreatedById] int NULL,
    [UpdatedById] int NULL,
    CONSTRAINT [PK_Categories] PRIMARY KEY ([Id]),
    CONSTRAINT [FK_Categories_Categories_ParentId] FOREIGN KEY ([ParentId]) REFERENCES [Categories] ([Id]) ON DELETE NO ACTION
);
GO

CREATE TABLE [Suppliers] (
    [Id] int NOT NULL IDENTITY,
    [Name] nvarchar(160) NOT NULL,
    [ContactName] nvarchar(160) NOT NULL DEFAULT N'',
    [Phone] nvarchar(40) NOT NULL DEFAULT N'',
    [Email] nvarchar(254) NOT NULL DEFAULT N'',
    [Notes] nvarchar(max) NOT NULL DEFAULT N'',
    [IsActive] bit NOT NULL DEFAULT CAST(1 AS bit),
    [CreatedAt] datetimeoffset NOT NULL DEFAULT (SYSUTCDATETIME()),
    [UpdatedAt] datetimeoffset NOT NULL DEFAULT (SYSUTCDATETIME()),
    [CreatedById] int NULL,
    [UpdatedById] int NULL,
    CONSTRAINT [PK_Suppliers] PRIMARY KEY ([Id])
);
GO

CREATE TABLE [Products] (
    [Id] int NOT NULL IDENTITY,
    [Name] nvarchar(220) NOT NULL,
    [Slug] nvarchar(240) NOT NULL,
    [CategoryId] int NOT NULL,
    [BrandId] int NULL,
    [SupplierId] int NULL,
    [ProductType] nvarchar(20) NOT NULL DEFAULT N'machinery',
    [Condition] nvarchar(20) NOT NULL DEFAULT N'not_applicable',
    [ShortDescription] nvarchar(280) NOT NULL DEFAULT N'',
    [Description] nvarchar(max) NOT NULL DEFAULT N'',
    [Model] nvarchar(120) NOT NULL DEFAULT N'',
    [Sku] nvarchar(120) NOT NULL DEFAULT N'',
    [Year] int NULL,
    [HoursMeter] int NULL,
    [Price] decimal(12,2) NULL,
    [PriceVisible] bit NOT NULL DEFAULT CAST(1 AS bit),
    [StockStatus] nvarchar(20) NOT NULL DEFAULT N'on_request',
    [IsFeatured] bit NOT NULL DEFAULT CAST(0 AS bit),
    [IsPublished] bit NOT NULL DEFAULT CAST(1 AS bit),
    [CreatedAt] datetimeoffset NOT NULL DEFAULT (SYSUTCDATETIME()),
    [UpdatedAt] datetimeoffset NOT NULL DEFAULT (SYSUTCDATETIME()),
    [CreatedById] int NULL,
    [UpdatedById] int NULL,
    CONSTRAINT [PK_Products] PRIMARY KEY ([Id]),
    CONSTRAINT [FK_Products_Brands_BrandId] FOREIGN KEY ([BrandId]) REFERENCES [Brands] ([Id]) ON DELETE NO ACTION,
    CONSTRAINT [FK_Products_Categories_CategoryId] FOREIGN KEY ([CategoryId]) REFERENCES [Categories] ([Id]) ON DELETE NO ACTION,
    CONSTRAINT [FK_Products_Suppliers_SupplierId] FOREIGN KEY ([SupplierId]) REFERENCES [Suppliers] ([Id]) ON DELETE NO ACTION
);
GO

CREATE TABLE [HomeSectionItems] (
    [Id] int NOT NULL IDENTITY,
    [Section] nvarchar(40) NOT NULL,
    [Position] int NOT NULL DEFAULT 1,
    [ProductId] int NOT NULL,
    [IsActive] bit NOT NULL DEFAULT CAST(1 AS bit),
    [CreatedAt] datetimeoffset NOT NULL DEFAULT (SYSUTCDATETIME()),
    [UpdatedAt] datetimeoffset NOT NULL DEFAULT (SYSUTCDATETIME()),
    [CreatedById] int NULL,
    [UpdatedById] int NULL,
    CONSTRAINT [PK_HomeSectionItems] PRIMARY KEY ([Id]),
    CONSTRAINT [FK_HomeSectionItems_Products_ProductId] FOREIGN KEY ([ProductId]) REFERENCES [Products] ([Id]) ON DELETE NO ACTION
);
GO

CREATE TABLE [ProductImages] (
    [Id] int NOT NULL IDENTITY,
    [ProductId] int NOT NULL,
    [Image] nvarchar(500) NOT NULL,
    [AltText] nvarchar(220) NOT NULL DEFAULT N'',
    [IsMain] bit NOT NULL DEFAULT CAST(0 AS bit),
    [Order] int NOT NULL DEFAULT 0,
    [CreatedAt] datetimeoffset NOT NULL DEFAULT (SYSUTCDATETIME()),
    [UpdatedAt] datetimeoffset NOT NULL DEFAULT (SYSUTCDATETIME()),
    [CreatedById] int NULL,
    [UpdatedById] int NULL,
    CONSTRAINT [PK_ProductImages] PRIMARY KEY ([Id]),
    CONSTRAINT [FK_ProductImages_Products_ProductId] FOREIGN KEY ([ProductId]) REFERENCES [Products] ([Id]) ON DELETE NO ACTION
);
GO

CREATE TABLE [ProductSpecs] (
    [Id] int NOT NULL IDENTITY,
    [ProductId] int NOT NULL,
    [Key] nvarchar(120) NOT NULL,
    [Value] nvarchar(220) NOT NULL,
    [Unit] nvarchar(40) NOT NULL DEFAULT N'',
    [Order] int NOT NULL DEFAULT 0,
    [CreatedAt] datetimeoffset NOT NULL DEFAULT (SYSUTCDATETIME()),
    [UpdatedAt] datetimeoffset NOT NULL DEFAULT (SYSUTCDATETIME()),
    [CreatedById] int NULL,
    [UpdatedById] int NULL,
    CONSTRAINT [PK_ProductSpecs] PRIMARY KEY ([Id]),
    CONSTRAINT [FK_ProductSpecs_Products_ProductId] FOREIGN KEY ([ProductId]) REFERENCES [Products] ([Id]) ON DELETE NO ACTION
);
GO

CREATE TABLE [Promotions] (
    [Id] int NOT NULL IDENTITY,
    [Title] nvarchar(180) NOT NULL,
    [Subtitle] nvarchar(280) NOT NULL DEFAULT N'',
    [ProductId] int NULL,
    [Image] nvarchar(500) NULL,
    [ButtonText] nvarchar(80) NOT NULL DEFAULT N'',
    [ButtonUrl] nvarchar(2048) NOT NULL DEFAULT N'',
    [IsActive] bit NOT NULL DEFAULT CAST(1 AS bit),
    [Order] int NOT NULL DEFAULT 0,
    [StartsAt] datetimeoffset NULL,
    [EndsAt] datetimeoffset NULL,
    [CreatedAt] datetimeoffset NOT NULL DEFAULT (SYSUTCDATETIME()),
    [UpdatedAt] datetimeoffset NOT NULL DEFAULT (SYSUTCDATETIME()),
    [CreatedById] int NULL,
    [UpdatedById] int NULL,
    CONSTRAINT [PK_Promotions] PRIMARY KEY ([Id]),
    CONSTRAINT [FK_Promotions_Products_ProductId] FOREIGN KEY ([ProductId]) REFERENCES [Products] ([Id]) ON DELETE NO ACTION
);
GO

CREATE TABLE [QuoteRequests] (
    [Id] int NOT NULL IDENTITY,
    [ProductId] int NULL,
    [CustomerName] nvarchar(160) NOT NULL,
    [CustomerPhone] nvarchar(40) NOT NULL,
    [CustomerEmail] nvarchar(254) NOT NULL DEFAULT N'',
    [CompanyName] nvarchar(160) NOT NULL DEFAULT N'',
    [City] nvarchar(120) NOT NULL DEFAULT N'',
    [PreferredContactMethod] nvarchar(20) NOT NULL DEFAULT N'',
    [Message] nvarchar(max) NOT NULL,
    [Status] nvarchar(20) NOT NULL DEFAULT N'new',
    [InternalNotes] nvarchar(max) NOT NULL DEFAULT N'',
    [SellerResponse] nvarchar(max) NOT NULL DEFAULT N'',
    [ContactedAt] datetimeoffset NULL,
    [QuotedAt] datetimeoffset NULL,
    [ClosedAt] datetimeoffset NULL,
    [CreatedAt] datetimeoffset NOT NULL DEFAULT (SYSUTCDATETIME()),
    [UpdatedAt] datetimeoffset NOT NULL DEFAULT (SYSUTCDATETIME()),
    [CreatedById] int NULL,
    [UpdatedById] int NULL,
    CONSTRAINT [PK_QuoteRequests] PRIMARY KEY ([Id]),
    CONSTRAINT [FK_QuoteRequests_Products_ProductId] FOREIGN KEY ([ProductId]) REFERENCES [Products] ([Id]) ON DELETE NO ACTION
);
GO

CREATE INDEX [IX_Brands_IsActive] ON [Brands] ([IsActive]);
GO

CREATE INDEX [IX_Brands_Name] ON [Brands] ([Name]);
GO

CREATE UNIQUE INDEX [IX_Brands_Slug] ON [Brands] ([Slug]);
GO

CREATE INDEX [IX_Categories_IsActive] ON [Categories] ([IsActive]);
GO

CREATE INDEX [IX_Categories_Order] ON [Categories] ([Order]);
GO

CREATE INDEX [IX_Categories_ParentId] ON [Categories] ([ParentId]);
GO

CREATE UNIQUE INDEX [IX_Categories_Slug] ON [Categories] ([Slug]);
GO

CREATE INDEX [IX_HomeSectionItems_IsActive] ON [HomeSectionItems] ([IsActive]);
GO

CREATE INDEX [IX_HomeSectionItems_ProductId] ON [HomeSectionItems] ([ProductId]);
GO

CREATE UNIQUE INDEX [IX_HomeSectionItems_Section_Position] ON [HomeSectionItems] ([Section], [Position]);
GO

CREATE UNIQUE INDEX [IX_HomeSectionItems_Section_ProductId] ON [HomeSectionItems] ([Section], [ProductId]);
GO

CREATE INDEX [IX_ProductImages_IsMain] ON [ProductImages] ([IsMain]);
GO

CREATE INDEX [IX_ProductImages_ProductId_Order_Id] ON [ProductImages] ([ProductId], [Order], [Id]);
GO

CREATE INDEX [IX_Products_BrandId] ON [Products] ([BrandId]);
GO

CREATE INDEX [IX_Products_CategoryId] ON [Products] ([CategoryId]);
GO

CREATE INDEX [IX_Products_Condition] ON [Products] ([Condition]);
GO

CREATE INDEX [IX_Products_IsFeatured] ON [Products] ([IsFeatured]);
GO

CREATE INDEX [IX_Products_IsPublished] ON [Products] ([IsPublished]);
GO

CREATE INDEX [IX_Products_ProductType] ON [Products] ([ProductType]);
GO

CREATE INDEX [IX_Products_Sku] ON [Products] ([Sku]);
GO

CREATE UNIQUE INDEX [IX_Products_Slug] ON [Products] ([Slug]);
GO

CREATE INDEX [IX_Products_StockStatus] ON [Products] ([StockStatus]);
GO

CREATE INDEX [IX_Products_SupplierId] ON [Products] ([SupplierId]);
GO

CREATE INDEX [IX_ProductSpecs_ProductId_Order_Id] ON [ProductSpecs] ([ProductId], [Order], [Id]);
GO

CREATE INDEX [IX_Promotions_EndsAt] ON [Promotions] ([EndsAt]);
GO

CREATE INDEX [IX_Promotions_IsActive] ON [Promotions] ([IsActive]);
GO

CREATE INDEX [IX_Promotions_Order] ON [Promotions] ([Order]);
GO

CREATE INDEX [IX_Promotions_ProductId] ON [Promotions] ([ProductId]);
GO

CREATE INDEX [IX_Promotions_StartsAt] ON [Promotions] ([StartsAt]);
GO

CREATE INDEX [IX_QuoteRequests_CreatedAt] ON [QuoteRequests] ([CreatedAt]);
GO

CREATE INDEX [IX_QuoteRequests_ProductId] ON [QuoteRequests] ([ProductId]);
GO

CREATE INDEX [IX_QuoteRequests_Status] ON [QuoteRequests] ([Status]);
GO

CREATE INDEX [IX_Suppliers_IsActive] ON [Suppliers] ([IsActive]);
GO

CREATE INDEX [IX_Suppliers_Name] ON [Suppliers] ([Name]);
GO

INSERT INTO [__EFMigrationsHistory] ([MigrationId], [ProductVersion])
VALUES (N'20260603182917_InitialCommercialSchema', N'8.0.6');
GO

COMMIT;
GO

BEGIN TRANSACTION;
GO

CREATE TABLE [AppUsers] (
    [Id] int NOT NULL IDENTITY,
    [Username] nvarchar(150) NOT NULL,
    [Email] nvarchar(254) NULL,
    [PasswordHash] nvarchar(500) NOT NULL,
    [Role] nvarchar(40) NOT NULL,
    [FullName] nvarchar(180) NULL,
    [IsActive] bit NOT NULL DEFAULT CAST(1 AS bit),
    [IsStaff] bit NOT NULL DEFAULT CAST(0 AS bit),
    [IsSuperuser] bit NOT NULL DEFAULT CAST(0 AS bit),
    [LastLoginAt] datetimeoffset NULL,
    [CreatedAt] datetimeoffset NOT NULL DEFAULT (SYSUTCDATETIME()),
    [UpdatedAt] datetimeoffset NOT NULL DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT [PK_AppUsers] PRIMARY KEY ([Id])
);
GO

CREATE TABLE [AppRefreshTokens] (
    [Id] int NOT NULL IDENTITY,
    [UserId] int NOT NULL,
    [TokenHash] nvarchar(128) NOT NULL,
    [ExpiresAt] datetimeoffset NOT NULL,
    [RevokedAt] datetimeoffset NULL,
    [CreatedAt] datetimeoffset NOT NULL DEFAULT (SYSUTCDATETIME()),
    [UpdatedAt] datetimeoffset NOT NULL DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT [PK_AppRefreshTokens] PRIMARY KEY ([Id]),
    CONSTRAINT [FK_AppRefreshTokens_AppUsers_UserId] FOREIGN KEY ([UserId]) REFERENCES [AppUsers] ([Id]) ON DELETE CASCADE
);
GO

CREATE INDEX [IX_Suppliers_CreatedById] ON [Suppliers] ([CreatedById]);
GO

CREATE INDEX [IX_Suppliers_UpdatedById] ON [Suppliers] ([UpdatedById]);
GO

CREATE INDEX [IX_QuoteRequests_CreatedById] ON [QuoteRequests] ([CreatedById]);
GO

CREATE INDEX [IX_QuoteRequests_UpdatedById] ON [QuoteRequests] ([UpdatedById]);
GO

CREATE INDEX [IX_Promotions_CreatedById] ON [Promotions] ([CreatedById]);
GO

CREATE INDEX [IX_Promotions_UpdatedById] ON [Promotions] ([UpdatedById]);
GO

CREATE INDEX [IX_ProductSpecs_CreatedById] ON [ProductSpecs] ([CreatedById]);
GO

CREATE INDEX [IX_ProductSpecs_UpdatedById] ON [ProductSpecs] ([UpdatedById]);
GO

CREATE INDEX [IX_Products_CreatedById] ON [Products] ([CreatedById]);
GO

CREATE INDEX [IX_Products_UpdatedById] ON [Products] ([UpdatedById]);
GO

CREATE INDEX [IX_ProductImages_CreatedById] ON [ProductImages] ([CreatedById]);
GO

CREATE INDEX [IX_ProductImages_UpdatedById] ON [ProductImages] ([UpdatedById]);
GO

CREATE INDEX [IX_HomeSectionItems_CreatedById] ON [HomeSectionItems] ([CreatedById]);
GO

CREATE INDEX [IX_HomeSectionItems_UpdatedById] ON [HomeSectionItems] ([UpdatedById]);
GO

CREATE INDEX [IX_Categories_CreatedById] ON [Categories] ([CreatedById]);
GO

CREATE INDEX [IX_Categories_UpdatedById] ON [Categories] ([UpdatedById]);
GO

CREATE INDEX [IX_Brands_CreatedById] ON [Brands] ([CreatedById]);
GO

CREATE INDEX [IX_Brands_UpdatedById] ON [Brands] ([UpdatedById]);
GO

CREATE UNIQUE INDEX [IX_AppRefreshTokens_TokenHash] ON [AppRefreshTokens] ([TokenHash]);
GO

CREATE INDEX [IX_AppRefreshTokens_UserId_ExpiresAt] ON [AppRefreshTokens] ([UserId], [ExpiresAt]);
GO

CREATE UNIQUE INDEX [IX_AppUsers_Email] ON [AppUsers] ([Email]) WHERE [Email] IS NOT NULL;
GO

CREATE INDEX [IX_AppUsers_IsActive] ON [AppUsers] ([IsActive]);
GO

CREATE INDEX [IX_AppUsers_Role] ON [AppUsers] ([Role]);
GO

CREATE UNIQUE INDEX [IX_AppUsers_Username] ON [AppUsers] ([Username]);
GO

ALTER TABLE [Brands] ADD CONSTRAINT [FK_Brands_AppUsers_CreatedById] FOREIGN KEY ([CreatedById]) REFERENCES [AppUsers] ([Id]);
GO

ALTER TABLE [Brands] ADD CONSTRAINT [FK_Brands_AppUsers_UpdatedById] FOREIGN KEY ([UpdatedById]) REFERENCES [AppUsers] ([Id]);
GO

ALTER TABLE [Categories] ADD CONSTRAINT [FK_Categories_AppUsers_CreatedById] FOREIGN KEY ([CreatedById]) REFERENCES [AppUsers] ([Id]);
GO

ALTER TABLE [Categories] ADD CONSTRAINT [FK_Categories_AppUsers_UpdatedById] FOREIGN KEY ([UpdatedById]) REFERENCES [AppUsers] ([Id]);
GO

ALTER TABLE [HomeSectionItems] ADD CONSTRAINT [FK_HomeSectionItems_AppUsers_CreatedById] FOREIGN KEY ([CreatedById]) REFERENCES [AppUsers] ([Id]);
GO

ALTER TABLE [HomeSectionItems] ADD CONSTRAINT [FK_HomeSectionItems_AppUsers_UpdatedById] FOREIGN KEY ([UpdatedById]) REFERENCES [AppUsers] ([Id]);
GO

ALTER TABLE [ProductImages] ADD CONSTRAINT [FK_ProductImages_AppUsers_CreatedById] FOREIGN KEY ([CreatedById]) REFERENCES [AppUsers] ([Id]);
GO

ALTER TABLE [ProductImages] ADD CONSTRAINT [FK_ProductImages_AppUsers_UpdatedById] FOREIGN KEY ([UpdatedById]) REFERENCES [AppUsers] ([Id]);
GO

ALTER TABLE [Products] ADD CONSTRAINT [FK_Products_AppUsers_CreatedById] FOREIGN KEY ([CreatedById]) REFERENCES [AppUsers] ([Id]);
GO

ALTER TABLE [Products] ADD CONSTRAINT [FK_Products_AppUsers_UpdatedById] FOREIGN KEY ([UpdatedById]) REFERENCES [AppUsers] ([Id]);
GO

ALTER TABLE [ProductSpecs] ADD CONSTRAINT [FK_ProductSpecs_AppUsers_CreatedById] FOREIGN KEY ([CreatedById]) REFERENCES [AppUsers] ([Id]);
GO

ALTER TABLE [ProductSpecs] ADD CONSTRAINT [FK_ProductSpecs_AppUsers_UpdatedById] FOREIGN KEY ([UpdatedById]) REFERENCES [AppUsers] ([Id]);
GO

ALTER TABLE [Promotions] ADD CONSTRAINT [FK_Promotions_AppUsers_CreatedById] FOREIGN KEY ([CreatedById]) REFERENCES [AppUsers] ([Id]);
GO

ALTER TABLE [Promotions] ADD CONSTRAINT [FK_Promotions_AppUsers_UpdatedById] FOREIGN KEY ([UpdatedById]) REFERENCES [AppUsers] ([Id]);
GO

ALTER TABLE [QuoteRequests] ADD CONSTRAINT [FK_QuoteRequests_AppUsers_CreatedById] FOREIGN KEY ([CreatedById]) REFERENCES [AppUsers] ([Id]);
GO

ALTER TABLE [QuoteRequests] ADD CONSTRAINT [FK_QuoteRequests_AppUsers_UpdatedById] FOREIGN KEY ([UpdatedById]) REFERENCES [AppUsers] ([Id]);
GO

ALTER TABLE [Suppliers] ADD CONSTRAINT [FK_Suppliers_AppUsers_CreatedById] FOREIGN KEY ([CreatedById]) REFERENCES [AppUsers] ([Id]);
GO

ALTER TABLE [Suppliers] ADD CONSTRAINT [FK_Suppliers_AppUsers_UpdatedById] FOREIGN KEY ([UpdatedById]) REFERENCES [AppUsers] ([Id]);
GO

INSERT INTO [__EFMigrationsHistory] ([MigrationId], [ProductVersion])
VALUES (N'20260604020543_AddAuthUsersAndAuditRelations', N'8.0.6');
GO

COMMIT;
GO

