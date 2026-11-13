.class public final Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;
.super Lcom/drakeet/multitype/MultiTypeAdapter;
.source "SourceFile"


# annotations
.annotation runtime Lasc/a;
.end annotation

.annotation system Ldalvik/annotation/MemberClasses;
    value = {
        Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter$a;
    }
.end annotation


# static fields
.field public static final Companion:Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter$a;
    .annotation build Lorg/jetbrains/annotations/NotNull;
    .end annotation
.end field


# instance fields
.field public final c:Ljava/lang/String;
    .annotation build Lorg/jetbrains/annotations/NotNull;
    .end annotation
.end field

.field public d:J

.field public e:J

.field public final f:Z

.field public final g:Lkotlin/j;
    .annotation build Lorg/jetbrains/annotations/NotNull;
    .end annotation
.end field

.field public h:Ljava/lang/String;
    .annotation build Lorg/jetbrains/annotations/NotNull;
    .end annotation
.end field


# direct methods
.method static constructor <clinit>()V
    .locals 1

    .line 1
    new-instance v0, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter$a;

    .line 2
    invoke-direct {v0}, Ljava/lang/Object;-><init>()V

    .line 4
    sput-object v0, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->Companion:Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter$a;

    .line 7
    return-void
    .line 9
.end method

.method public constructor <init>()V
    .locals 2

    .line 1
    const/4 v0, 0x0

    const/4 v1, 0x1

    invoke-direct {p0, v0, v1, v0}, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;-><init>(Ljava/lang/String;ILkotlin/jvm/internal/DefaultConstructorMarker;)V

    return-void
.end method

.method public constructor <init>(Ljava/lang/String;)V
    .locals 6
    .param p1    # Ljava/lang/String;
        .annotation build Lorg/jetbrains/annotations/NotNull;
        .end annotation
    .end param

    const/4 v1, 0x0

    const/4 v2, 0x0

    const/4 v3, 0x0

    const/4 v4, 0x7

    const/4 v5, 0x0

    move-object v0, p0

    .line 3
    invoke-direct/range {v0 .. v5}, Lcom/drakeet/multitype/MultiTypeAdapter;-><init>(Ljava/util/List;ILha/o;ILkotlin/jvm/internal/DefaultConstructorMarker;)V

    iput-object p1, p0, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->c:Ljava/lang/String;

    .line 4
    invoke-static {}, Lkb2/b;->b()Z

    move-result p1

    iput-boolean p1, p0, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->f:Z

    .line 5
    new-instance p1, Ln0d/f1;

    .line 6
    invoke-direct {p1}, Ljava/lang/Object;-><init>()V

    .line 7
    invoke-static {p1}, Lkotlin/k;->b(Lkotlin/jvm/functions/Function0;)Lkotlin/j;

    move-result-object p1

    iput-object p1, p0, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->g:Lkotlin/j;

    const-string p1, ""

    iput-object p1, p0, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->h:Ljava/lang/String;

    return-void
.end method

.method public synthetic constructor <init>(Ljava/lang/String;ILkotlin/jvm/internal/DefaultConstructorMarker;)V
    .locals 0

    and-int/lit8 p2, p2, 0x1

    if-eqz p2, :cond_0

    const-string p1, "home_page_feed"

    .line 2
    :cond_0
    invoke-direct {p0, p1}, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;-><init>(Ljava/lang/String;)V

    return-void
.end method


# virtual methods
.method public final J0(Ljava/lang/String;)V
    .locals 11
    .param p1    # Ljava/lang/String;
        .annotation build Lorg/jetbrains/annotations/NotNull;
        .end annotation
    .end param

    .line 1
    iget-object v0, p0, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->g:Lkotlin/j;

    .line 2
    check-cast v0, Lkotlin/q;

    .line 4
    invoke-virtual {v0}, Lkotlin/q;->getValue()Ljava/lang/Object;

    .line 6
    move-result-object v0

    .line 9
    check-cast v0, Ljava/lang/Boolean;

    .line 10
    invoke-virtual {v0}, Ljava/lang/Boolean;->booleanValue()Z

    .line 12
    move-result v0

    .line 15
    const-string v1, "FeedCustomMultiTypeAdapter"

    .line 16
    if-nez v0, :cond_0

    .line 18
    const-string p1, "reportCachePoolInfo() not enableReportPoolInfo"

    .line 20
    invoke-static {v1, p1}, Ljad/f;->r(Ljava/lang/String;Ljava/lang/String;)V

    .line 22
    return-void

    .line 25
    :cond_0
    iget-wide v2, p0, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->e:J

    .line 26
    const-wide/16 v4, 0x64

    .line 28
    cmp-long v0, v2, v4

    .line 30
    if-gtz v0, :cond_1

    .line 32
    const-string p1, "reportCachePoolInfo() onBindViewHolderCount <100, not report"

    .line 34
    invoke-static {v1, p1}, Ljad/f;->r(Ljava/lang/String;Ljava/lang/String;)V

    .line 36
    return-void

    .line 39
    :cond_1
    iget-object v0, p0, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->h:Ljava/lang/String;

    .line 40
    invoke-virtual {v0}, Ljava/lang/String;->length()I

    .line 42
    move-result v0

    .line 45
    iget-object v2, p0, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->c:Ljava/lang/String;

    .line 46
    if-nez v0, :cond_6

    .line 48
    const-string v0, "home_page_feed"

    .line 50
    invoke-static {v2, v0}, Lkotlin/jvm/internal/Intrinsics;->f(Ljava/lang/Object;Ljava/lang/Object;)Z

    .line 52
    move-result v0

    .line 55
    const/4 v3, 0x0

    .line 56
    if-eqz v0, :cond_2

    .line 57
    sget-object v0, Lrwc/b;->a:Lrwc/b;

    .line 59
    invoke-virtual {v0}, Lrwc/b;->d()Z

    .line 61
    move-result v4

    .line 64
    if-eqz v4, :cond_3

    .line 65
    invoke-virtual {v0}, Lrwc/b;->k()I

    .line 67
    move-result v0

    .line 70
    invoke-static {v0}, Ljava/lang/Integer;->valueOf(I)Ljava/lang/Integer;

    .line 71
    move-result-object v3

    .line 74
    goto :goto_0

    .line 75
    :cond_2
    const-string v0, "home_sub_channel"

    .line 76
    invoke-static {v2, v0}, Lkotlin/jvm/internal/Intrinsics;->f(Ljava/lang/Object;Ljava/lang/Object;)Z

    .line 78
    move-result v0

    .line 81
    if-eqz v0, :cond_3

    .line 82
    sget-object v0, Lrwc/b;->a:Lrwc/b;

    .line 84
    invoke-virtual {v0}, Lrwc/b;->e()Z

    .line 86
    move-result v4

    .line 89
    if-eqz v4, :cond_3

    .line 90
    invoke-virtual {v0}, Lrwc/b;->l()I

    .line 92
    move-result v0

    .line 95
    invoke-static {v0}, Ljava/lang/Integer;->valueOf(I)Ljava/lang/Integer;

    .line 96
    move-result-object v3

    .line 99
    :cond_3
    :goto_0
    if-eqz v3, :cond_4

    .line 100
    invoke-virtual {v3}, Ljava/lang/Number;->intValue()I

    .line 102
    move-result v0

    .line 105
    new-instance v3, Ljava/lang/StringBuilder;

    .line 106
    const-string v4, "pool_"

    .line 108
    invoke-direct {v3, v4}, Ljava/lang/StringBuilder;-><init>(Ljava/lang/String;)V

    .line 110
    invoke-virtual {v3, v0}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;

    .line 113
    invoke-virtual {v3}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    .line 116
    move-result-object v0

    .line 119
    if-nez v0, :cond_5

    .line 120
    :cond_4
    const-string v0, "old_default"

    .line 122
    :cond_5
    iput-object v0, p0, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->h:Ljava/lang/String;

    .line 124
    :cond_6
    iget-wide v3, p0, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->d:J

    .line 126
    iget-wide v5, p0, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->e:J

    .line 128
    const-wide/16 v7, 0x0

    .line 130
    iput-wide v7, p0, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->d:J

    .line 132
    iput-wide v7, p0, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->e:J

    .line 134
    cmp-long v0, v5, v7

    .line 136
    if-lez v0, :cond_7

    .line 138
    sub-long v7, v5, v3

    .line 140
    long-to-float v0, v7

    .line 142
    long-to-float v7, v5

    .line 143
    div-float/2addr v0, v7

    .line 144
    goto :goto_1

    .line 145
    :cond_7
    const/4 v0, 0x0

    .line 146
    :goto_1
    new-instance v7, Lcom/xingin/android/apm_core/TrackerEventDetail$b;

    .line 147
    invoke-direct {v7}, Lcom/xingin/android/apm_core/TrackerEventDetail$b;-><init>()V

    .line 149
    const-string/jumbo v8, "sns_rv_pool_count_info"

    .line 152
    iput-object v8, v7, Lcom/xingin/android/apm_core/TrackerEventDetail$b;->b:Ljava/lang/String;

    .line 155
    const-wide v8, 0x3f847ae147ae147bL    # 0.01

    .line 157
    invoke-static {v8, v9}, Ljava/lang/Double;->valueOf(D)Ljava/lang/Double;

    .line 162
    move-result-object v8

    .line 165
    iput-object v8, v7, Lcom/xingin/android/apm_core/TrackerEventDetail$b;->c:Ljava/lang/Double;

    .line 166
    const-string/jumbo v8, "source"

    .line 168
    invoke-virtual {v7, v8, v2}, Lcom/xingin/android/apm_core/TrackerEventDetail$b;->g(Ljava/lang/String;Ljava/lang/String;)Lcom/xingin/android/apm_core/TrackerEventDetail$b;

    .line 171
    const-string/jumbo v8, "sub_type"

    .line 174
    iget-object v9, p0, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->h:Ljava/lang/String;

    .line 177
    invoke-virtual {v7, v8, v9}, Lcom/xingin/android/apm_core/TrackerEventDetail$b;->g(Ljava/lang/String;Ljava/lang/String;)Lcom/xingin/android/apm_core/TrackerEventDetail$b;

    .line 179
    const-string v8, "no_hit_cache_count"

    .line 182
    invoke-virtual {v7, v8, v3, v4}, Lcom/xingin/android/apm_core/TrackerEventDetail$b;->f(Ljava/lang/String;J)Lcom/xingin/android/apm_core/TrackerEventDetail$b;

    .line 184
    const-string v8, "hit_cache_count"

    .line 187
    sub-long v9, v5, v3

    .line 189
    invoke-virtual {v7, v8, v9, v10}, Lcom/xingin/android/apm_core/TrackerEventDetail$b;->f(Ljava/lang/String;J)Lcom/xingin/android/apm_core/TrackerEventDetail$b;

    .line 191
    const-string/jumbo v8, "total_count"

    .line 194
    invoke-virtual {v7, v8, v5, v6}, Lcom/xingin/android/apm_core/TrackerEventDetail$b;->f(Ljava/lang/String;J)Lcom/xingin/android/apm_core/TrackerEventDetail$b;

    .line 197
    const-string v8, "hit_cache_rate"

    .line 200
    invoke-virtual {v7, v8, v0}, Lcom/xingin/android/apm_core/TrackerEventDetail$b;->d(Ljava/lang/String;F)Lcom/xingin/android/apm_core/TrackerEventDetail$b;

    .line 202
    new-instance v8, Ljava/lang/StringBuilder;

    .line 205
    const-string v9, "reportCachePoolInfo() source="

    .line 207
    invoke-direct {v8, v9}, Ljava/lang/StringBuilder;-><init>(Ljava/lang/String;)V

    .line 209
    invoke-virtual {v8, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    .line 212
    const-string v2, " invoker="

    .line 215
    invoke-virtual {v8, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    .line 217
    invoke-virtual {v8, p1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    .line 220
    const-string p1, " noHitCount: "

    .line 223
    invoke-virtual {v8, p1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    .line 225
    invoke-virtual {v8, v3, v4}, Ljava/lang/StringBuilder;->append(J)Ljava/lang/StringBuilder;

    .line 228
    const-string p1, "; totalCount: "

    .line 231
    invoke-virtual {v8, p1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    .line 233
    invoke-virtual {v8, v5, v6}, Ljava/lang/StringBuilder;->append(J)Ljava/lang/StringBuilder;

    .line 236
    const-string p1, ", hitRate="

    .line 239
    invoke-virtual {v8, p1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    .line 241
    invoke-virtual {v8, v0}, Ljava/lang/StringBuilder;->append(F)Ljava/lang/StringBuilder;

    .line 244
    invoke-virtual {v8}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    .line 247
    move-result-object p1

    .line 250
    invoke-static {v1, p1}, Ljad/f;->r(Ljava/lang/String;Ljava/lang/String;)V

    .line 251
    sget-object p1, Lcom/xingin/android/apm_core/c;->m:Lcom/xingin/android/apm_core/c;

    .line 254
    invoke-virtual {p1, v7}, Lcom/xingin/android/apm_core/j;->f(Lcom/xingin/android/apm_core/TrackerEventDetail$b;)V

    .line 256
    return-void
    .line 259
.end method

.method public onBindViewHolder(Landroidx/recyclerview/widget/RecyclerView$ViewHolder;ILjava/util/List;)V
    .locals 4
    .param p1    # Landroidx/recyclerview/widget/RecyclerView$ViewHolder;
        .annotation build Lorg/jetbrains/annotations/NotNull;
        .end annotation
    .end param
    .param p3    # Ljava/util/List;
        .annotation build Lorg/jetbrains/annotations/NotNull;
        .end annotation
    .end param
    .annotation system Ldalvik/annotation/Signature;
        value = {
            "(",
            "Landroidx/recyclerview/widget/RecyclerView$ViewHolder;",
            "I",
            "Ljava/util/List<",
            "+",
            "Ljava/lang/Object;",
            ">;)V"
        }
    .end annotation

    .line 1
    iget-boolean v0, p0, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->f:Z

    .line 2
    if-eqz v0, :cond_0

    .line 4
    new-instance v0, Ljava/lang/StringBuilder;

    .line 6
    const-string v1, "onBindViewHolder() position: "

    .line 8
    invoke-direct {v0, v1}, Ljava/lang/StringBuilder;-><init>(Ljava/lang/String;)V

    .line 10
    invoke-virtual {v0, p2}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;

    .line 13
    const-string v1, "; payloads="

    .line 16
    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    .line 18
    invoke-virtual {v0, p3}, Ljava/lang/StringBuilder;->append(Ljava/lang/Object;)Ljava/lang/StringBuilder;

    .line 21
    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    .line 24
    move-result-object v0

    .line 27
    const-string v1, "FeedCustomMultiTypeAdapter"

    .line 28
    invoke-static {v1, v0}, Ljad/f;->r(Ljava/lang/String;Ljava/lang/String;)V

    .line 30
    :cond_0
    iget-wide v0, p0, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->e:J

    .line 33
    const-wide/16 v2, 0x1

    .line 35
    add-long/2addr v0, v2

    .line 37
    iput-wide v0, p0, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->e:J

    .line 38
    invoke-super {p0, p1, p2, p3}, Lcom/drakeet/multitype/MultiTypeAdapter;->onBindViewHolder(Landroidx/recyclerview/widget/RecyclerView$ViewHolder;ILjava/util/List;)V

    .line 40
    iget-object p1, p0, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->g:Lkotlin/j;

    .line 43
    check-cast p1, Lkotlin/q;

    .line 45
    invoke-virtual {p1}, Lkotlin/q;->getValue()Ljava/lang/Object;

    .line 47
    move-result-object p1

    .line 50
    check-cast p1, Ljava/lang/Boolean;

    .line 51
    invoke-virtual {p1}, Ljava/lang/Boolean;->booleanValue()Z

    .line 53
    move-result p1

    .line 56
    if-eqz p1, :cond_1

    .line 57
    iget-wide p1, p0, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->e:J

    .line 59
    const-wide/16 v0, 0x64

    .line 61
    cmp-long p3, p1, v0

    .line 63
    if-lez p3, :cond_1

    .line 65
    const-string p1, "MAX_COUNT"

    .line 67
    invoke-virtual {p0, p1}, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->J0(Ljava/lang/String;)V

    .line 69
    :cond_1
    return-void
    .line 72
.end method

.method public onCreateViewHolder(Landroid/view/ViewGroup;I)Landroidx/recyclerview/widget/RecyclerView$ViewHolder;
    .locals 4
    .param p1    # Landroid/view/ViewGroup;
        .annotation build Lorg/jetbrains/annotations/NotNull;
        .end annotation
    .end param
    .annotation build Lorg/jetbrains/annotations/NotNull;
    .end annotation

    .line 1
    iget-boolean v0, p0, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->f:Z

    .line 2
    if-eqz v0, :cond_0

    .line 4
    new-instance v0, Ljava/lang/StringBuilder;

    .line 6
    const-string v1, "onCreateViewHolder() indexViewType: "

    .line 8
    invoke-direct {v0, v1}, Ljava/lang/StringBuilder;-><init>(Ljava/lang/String;)V

    .line 10
    invoke-virtual {v0, p2}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;

    .line 13
    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    .line 16
    move-result-object v0

    .line 19
    const-string v1, "FeedCustomMultiTypeAdapter"

    .line 20
    invoke-static {v1, v0}, Ljad/f;->r(Ljava/lang/String;Ljava/lang/String;)V

    .line 22
    :cond_0
    iget-wide v0, p0, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->d:J

    .line 25
    const-wide/16 v2, 0x1

    .line 27
    add-long/2addr v0, v2

    .line 29
    iput-wide v0, p0, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->d:J

    .line 30
    invoke-super {p0, p1, p2}, Lcom/drakeet/multitype/MultiTypeAdapter;->onCreateViewHolder(Landroid/view/ViewGroup;I)Landroidx/recyclerview/widget/RecyclerView$ViewHolder;

    .line 32
    move-result-object p1

    .line 35
    return-object p1
    .line 36
.end method

.method public onViewRecycled(Landroidx/recyclerview/widget/RecyclerView$ViewHolder;)V
    .locals 2
    .param p1    # Landroidx/recyclerview/widget/RecyclerView$ViewHolder;
        .annotation build Lorg/jetbrains/annotations/NotNull;
        .end annotation
    .end param

    .line 1
    invoke-super {p0, p1}, Lcom/drakeet/multitype/MultiTypeAdapter;->onViewRecycled(Landroidx/recyclerview/widget/RecyclerView$ViewHolder;)V

    .line 2
    iget-boolean v0, p0, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->f:Z

    .line 5
    if-eqz v0, :cond_0

    .line 7
    invoke-virtual {p1}, Landroidx/recyclerview/widget/RecyclerView$ViewHolder;->getAdapterPosition()I

    .line 9
    move-result p1

    .line 12
    new-instance v0, Ljava/lang/StringBuilder;

    .line 13
    const-string v1, "onViewRecycled() holder: "

    .line 15
    invoke-direct {v0, v1}, Ljava/lang/StringBuilder;-><init>(Ljava/lang/String;)V

    .line 17
    invoke-virtual {v0, p1}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;

    .line 20
    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    .line 23
    move-result-object p1

    .line 26
    const-string v0, "FeedCustomMultiTypeAdapter"

    .line 27
    invoke-static {v0, p1}, Ljad/f;->r(Ljava/lang/String;Ljava/lang/String;)V

    .line 29
    :cond_0
    return-void
    .line 32
.end method
