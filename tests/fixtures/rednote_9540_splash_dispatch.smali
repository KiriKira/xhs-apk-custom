.class public final Lqz/f;
.super Ljava/lang/Object;
.source "SourceFile"


# annotations
.annotation runtime Lasc/a;
.end annotation

.annotation system Ldalvik/annotation/MemberClasses;
    value = {
        Lqz/f$a;
    }
.end annotation


# static fields
.field public static final Companion:Lqz/f$a;
    .annotation build Lorg/jetbrains/annotations/NotNull;
    .end annotation
.end field

.field public static final i:Lkotlin/j;
    .annotation system Ldalvik/annotation/Signature;
        value = {
            "Lkotlin/j<",
            "Lqz/f;",
            ">;"
        }
    .end annotation

    .annotation build Lorg/jetbrains/annotations/NotNull;
    .end annotation
.end field


# instance fields
.field public a:Lcom/xingin/advert/intersitial/bean/SplashAd;
    .annotation build Lorg/jetbrains/annotations/Nullable;
    .end annotation
.end field

.field public final b:J

.field public final c:Ljava/util/concurrent/locks/ReentrantLock;
    .annotation build Lorg/jetbrains/annotations/NotNull;
    .end annotation
.end field

.field public final d:Ljava/util/concurrent/CountDownLatch;
    .annotation build Lorg/jetbrains/annotations/NotNull;
    .end annotation
.end field

.field public volatile e:Z

.field public volatile f:Z

.field public final g:J

.field public final h:Z


# direct methods
.method static constructor <clinit>()V
    .locals 2

    .line 1
    new-instance v0, Lqz/f$a;

    .line 2
    invoke-direct {v0}, Ljava/lang/Object;-><init>()V

    .line 4
    sput-object v0, Lqz/f;->Companion:Lqz/f$a;

    .line 7
    sget-object v0, Lkotlin/l;->SYNCHRONIZED:Lkotlin/l;

    .line 9
    new-instance v1, Lqz/e;

    .line 11
    invoke-direct {v1}, Ljava/lang/Object;-><init>()V

    .line 13
    invoke-static {v0, v1}, Lkotlin/k;->a(Lkotlin/l;Lkotlin/jvm/functions/Function0;)Lkotlin/j;

    .line 16
    move-result-object v0

    .line 19
    sput-object v0, Lqz/f;->i:Lkotlin/j;

    .line 20
    return-void
    .line 22
.end method

.method public constructor <init>()V
    .locals 6

    .line 1
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    .line 2
    const-wide/16 v0, 0x3e8

    .line 5
    iput-wide v0, p0, Lqz/f;->b:J

    .line 7
    new-instance v0, Ljava/util/concurrent/locks/ReentrantLock;

    .line 9
    invoke-direct {v0}, Ljava/util/concurrent/locks/ReentrantLock;-><init>()V

    .line 11
    iput-object v0, p0, Lqz/f;->c:Ljava/util/concurrent/locks/ReentrantLock;

    .line 14
    new-instance v0, Ljava/util/concurrent/CountDownLatch;

    .line 16
    const/4 v1, 0x1

    .line 18
    invoke-direct {v0, v1}, Ljava/util/concurrent/CountDownLatch;-><init>(I)V

    .line 19
    iput-object v0, p0, Lqz/f;->d:Ljava/util/concurrent/CountDownLatch;

    .line 22
    sget-object v0, Lcom/xingin/advert/exp/AdvertExp;->a:Lcom/xingin/advert/exp/AdvertExp;

    .line 24
    sget-object v0, Lgr/k;->a:Lgr/j;

    .line 26
    const-wide/16 v2, 0x190

    .line 28
    invoke-static {v2, v3}, Ljava/lang/Long;->valueOf(J)Ljava/lang/Long;

    .line 30
    move-result-object v2

    .line 33
    new-instance v3, Ldc2/g;

    .line 34
    invoke-direct {v3}, Ldc2/g;-><init>()V

    .line 36
    invoke-virtual {v3}, Ldc2/g;->getType()Ljava/lang/reflect/Type;

    .line 39
    move-result-object v3

    .line 42
    check-cast v0, Lkr/h;

    .line 43
    const-string v4, "andr_splash_ad_countdown_time_v2"

    .line 45
    invoke-virtual {v0, v4, v3, v2}, Lkr/h;->j(Ljava/lang/String;Ljava/lang/reflect/Type;Ljava/lang/Object;)Ljava/lang/Object;

    .line 47
    move-result-object v0

    .line 50
    check-cast v0, Ljava/lang/Number;

    .line 51
    invoke-virtual {v0}, Ljava/lang/Number;->longValue()J

    .line 53
    move-result-wide v2

    .line 56
    iput-wide v2, p0, Lqz/f;->g:J

    .line 57
    const-wide/16 v4, 0x0

    .line 59
    cmp-long v0, v2, v4

    .line 61
    if-lez v0, :cond_0

    .line 63
    goto :goto_0

    .line 65
    :cond_0
    const/4 v1, 0x0

    .line 66
    :goto_0
    iput-boolean v1, p0, Lqz/f;->h:Z

    .line 67
    return-void
    .line 69
.end method


# virtual methods
.method public final a(Lwe/o;Lkotlin/jvm/functions/Function1;Lkotlin/jvm/functions/Function1;)V
    .locals 4
    .annotation system Ldalvik/annotation/Signature;
        value = {
            "(",
            "Lwe/o<",
            "Lcom/xingin/advert/intersitial/bean/SplashAd;",
            ">;",
            "Lkotlin/jvm/functions/Function1<",
            "-",
            "Lcom/xingin/advert/intersitial/bean/SplashAd;",
            "Lkotlin/Unit;",
            ">;",
            "Lkotlin/jvm/functions/Function1<",
            "-",
            "Ljava/lang/Integer;",
            "Lkotlin/Unit;",
            ">;)V"
        }
    .end annotation

    .line 1
    invoke-virtual {p1}, Lwe/o;->c()Z

    .line 2
    move-result v0

    .line 5
    const-string v1, "end"

    .line 6
    const-string v2, "load_end"

    .line 8
    const-string v3, "post_end"

    .line 10
    if-eqz v0, :cond_0

    .line 12
    sget-object p3, Lp60/c3;->a:Lp60/c3;

    .line 14
    invoke-virtual {p3, v3}, Lp60/c3;->a(Ljava/lang/String;)V

    .line 16
    invoke-virtual {p3, v2}, Lp60/c3;->a(Ljava/lang/String;)V

    .line 19
    invoke-virtual {p1}, Lwe/o;->b()Ljava/lang/Object;

    .line 22
    move-result-object p1

    .line 25
    invoke-interface {p2, p1}, Lkotlin/jvm/functions/Function1;->invoke(Ljava/lang/Object;)Ljava/lang/Object;

    .line 26
    const-string p1, "load splash ad success"

    .line 29
    invoke-static {p1}, La30/a;->a(Ljava/lang/String;)V

    .line 31
    sget-object p1, Lp60/y2;->a:Lp60/y2;

    .line 34
    const-string p2, "load_ad_success"

    .line 36
    invoke-virtual {p1, p2}, Lp60/y2;->a(Ljava/lang/String;)V

    .line 38
    sget-object p1, Lp60/v2;->a:Lp60/v2;

    .line 41
    invoke-virtual {p1, v1}, Lp60/v2;->d(Ljava/lang/String;)V

    .line 43
    goto :goto_0

    .line 46
    :cond_0
    sget-object p1, Lc00/f;->a:Lc00/f;

    .line 47
    invoke-virtual {p1}, Lc00/f;->a()V

    .line 49
    sget-object p1, Lp60/c3;->a:Lp60/c3;

    .line 52
    invoke-virtual {p1, v3}, Lp60/c3;->a(Ljava/lang/String;)V

    .line 54
    invoke-virtual {p1, v2}, Lp60/c3;->a(Ljava/lang/String;)V

    .line 57
    sget-object p1, Lp60/v2;->a:Lp60/v2;

    .line 60
    invoke-virtual {p1, v1}, Lp60/v2;->d(Ljava/lang/String;)V

    .line 62
    const/4 p1, 0x0

    .line 65
    invoke-static {p1}, Ljava/lang/Integer;->valueOf(I)Ljava/lang/Integer;

    .line 66
    move-result-object p1

    .line 69
    invoke-interface {p3, p1}, Lkotlin/jvm/functions/Function1;->invoke(Ljava/lang/Object;)Ljava/lang/Object;

    .line 70
    sget-object p1, La30/a;->a:La30/a;

    .line 73
    sget-object p1, Ljad/a;->AD_LOG:Ljad/a;

    .line 75
    const-string p2, "AdLog"

    .line 77
    const-string p3, "no splash ad"

    .line 79
    invoke-static {p1, p2, p3}, Ljad/f;->z(Ljad/a;Ljava/lang/String;Ljava/lang/String;)V

    .line 81
    :goto_0
    return-void
    .line 84
.end method

.method public final b()V
    .locals 1

    .line 1
    const/4 v0, 0x0

    .line 2
    iput-object v0, p0, Lqz/f;->a:Lcom/xingin/advert/intersitial/bean/SplashAd;

    .line 3
    const/4 v0, 0x1

    .line 5
    iput-boolean v0, p0, Lqz/f;->f:Z

    .line 6
    iget-boolean v0, p0, Lqz/f;->h:Z

    .line 8
    if-nez v0, :cond_1

    .line 10
    iget-object v0, p0, Lqz/f;->c:Ljava/util/concurrent/locks/ReentrantLock;

    .line 12
    invoke-virtual {v0}, Ljava/util/concurrent/locks/ReentrantLock;->isLocked()Z

    .line 14
    move-result v0

    .line 17
    if-eqz v0, :cond_0

    .line 18
    iget-object v0, p0, Lqz/f;->c:Ljava/util/concurrent/locks/ReentrantLock;

    .line 20
    invoke-virtual {v0}, Ljava/util/concurrent/locks/ReentrantLock;->unlock()V

    .line 22
    :cond_0
    const-string v0, "splashLoadError -> use ReentrantLock , unlock()"

    .line 25
    invoke-static {v0}, La30/a;->a(Ljava/lang/String;)V

    .line 27
    goto :goto_0

    .line 30
    :cond_1
    iget-object v0, p0, Lqz/f;->d:Ljava/util/concurrent/CountDownLatch;

    .line 31
    invoke-virtual {v0}, Ljava/util/concurrent/CountDownLatch;->countDown()V

    .line 33
    const-string v0, "splashLoadError -> use CountdownLatch , unlock()"

    .line 36
    invoke-static {v0}, La30/a;->a(Ljava/lang/String;)V

    .line 38
    :goto_0
    return-void
    .line 41
.end method
